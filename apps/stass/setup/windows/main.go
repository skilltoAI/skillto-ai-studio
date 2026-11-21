//go:build windows

// The release builder appends a ZIP and footer to this executable before signing.
package main

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	"debug/pe"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

var archiveDigest, manifestDigest string

const trailerMagic = "STASSZIP"

func payload(executable *os.File) (*zip.Reader, error) {
	info, err := executable.Stat()
	if err != nil {
		return nil, err
	}
	end := info.Size()
	image, err := pe.NewFile(executable)
	if err != nil {
		return nil, err
	}
	header, ok := image.OptionalHeader.(*pe.OptionalHeader64)
	if !ok {
		return nil, errors.New("expected a Windows x64 installer")
	}
	if certificate := header.DataDirectory[pe.IMAGE_DIRECTORY_ENTRY_SECURITY]; certificate.Size != 0 {
		end = int64(certificate.VirtualAddress)
	}
	// Authenticode aligns the certificate table to an 8-byte boundary.
	for padding := int64(0); padding < 8 && end >= 16+padding; padding++ {
		var footer [16]byte
		zipEnd := end - 16 - padding
		if _, err := executable.ReadAt(footer[:], zipEnd); err != nil {
			return nil, err
		}
		if !bytes.Equal(footer[8:], []byte(trailerMagic)) {
			continue
		}
		start := int64(binary.LittleEndian.Uint64(footer[:8]))
		if start <= 0 || start >= zipEnd {
			return nil, errors.New("invalid installer archive location")
		}
		section := io.NewSectionReader(executable, start, zipEnd-start)
		hash := sha256.New()
		if _, err := io.Copy(hash, section); err != nil {
			return nil, err
		}
		if hex.EncodeToString(hash.Sum(nil)) != archiveDigest {
			return nil, errors.New("installer archive checksum mismatch")
		}
		return zip.NewReader(section, section.Size())
	}
	return nil, errors.New("installer archive is missing")
}

func unpack(archive *zip.Reader, directory string) error {
	for _, file := range archive.File {
		if !fs.ValidPath(file.Name) || file.Name == "." || path.Clean(file.Name) != file.Name ||
			strings.ContainsAny(file.Name, `\:`) || !file.Mode().IsRegular() {
			return errors.New("invalid installer archive entry")
		}
		destination := filepath.Join(directory, filepath.FromSlash(file.Name))
		if err := os.MkdirAll(filepath.Dir(destination), 0700); err != nil {
			return err
		}
		if err := extractFile(file, destination); err != nil {
			return err
		}
	}
	return nil
}

func extractFile(file *zip.File, destination string) error {
	source, err := file.Open()
	if err != nil {
		return err
	}
	defer source.Close()
	target, err := os.OpenFile(destination, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	_, copyErr := io.Copy(target, source)
	return errors.Join(copyErr, target.Close())
}

func run() ([]byte, error) {
	root := flag.String("root", "", "Installation root")
	port := flag.Int("port", 0, "Loopback port")
	host := flag.String("host", "codex", "codex, claude or none")
	skillsRoot := flag.String("skills-root", "", "Override the host Skills directory")
	register := flag.Bool("register-mcp", false, "Register the authorized local Codex MCP")
	noOpen := flag.Bool("no-open", false, "Skip starting the desktop window")
	resultFile := flag.String("result-file", "", "Write a JSON installation receipt")
	flag.Parse()
	if *host != "codex" && *host != "claude" && *host != "none" || *port < 0 || *port > 65535 {
		return nil, errors.New("invalid installation host or port")
	}
	name, err := os.Executable()
	if err != nil {
		return nil, err
	}
	executable, err := os.Open(name)
	if err != nil {
		return nil, err
	}
	defer executable.Close()
	archive, err := payload(executable)
	if err != nil {
		return nil, err
	}
	installRoot := *root
	if installRoot == "" {
		localData := os.Getenv("LOCALAPPDATA")
		if localData == "" {
			return nil, errors.New("无法定位用户安装目录，请用 --root 指定安装路径")
		}
		installRoot = filepath.Join(localData, "Skillto.ai", "Studio")
	}
	installRoot, err = filepath.Abs(installRoot)
	if err != nil {
		return nil, err
	}
	staging := filepath.Join(installRoot, "staging")
	if err := os.MkdirAll(staging, 0700); err != nil {
		return nil, fmt.Errorf("无法创建解包目录 %s: %w", staging, err)
	}
	directory, err := os.MkdirTemp(staging, "setup-")
	if err != nil {
		return nil, fmt.Errorf("无法解包到 %s。请检查剩余空间，或用 --root 指定其他可写盘符: %w", staging, err)
	}
	defer os.RemoveAll(directory)
	if err := unpack(archive, directory); err != nil {
		return nil, fmt.Errorf("无法解包到 %s。请检查剩余空间，或用 --root 指定其他可写盘符: %w", staging, err)
	}
	receipt := directory + "-result.json"
	defer os.Remove(receipt)
	args := []string{"-B", filepath.Join(directory, "program", "offline_install.py"), "--setup",
		"--package", directory, "--manifest-sha256", manifestDigest, "--result-file", receipt}
	args = append(args, "--root", installRoot)
	if *port != 0 {
		args = append(args, "--port", fmt.Sprint(*port))
	}
	if *host != "none" {
		args = append(args, "--host", *host)
	}
	if *skillsRoot != "" {
		args = append(args, "--skills-root", *skillsRoot)
	}
	if *register {
		args = append(args, "--register-mcp")
	}
	if *noOpen {
		args = append(args, "--no-open")
	}
	command := exec.Command(filepath.Join(directory, "runtime", "python.exe"), args...)
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	output, runErr := command.CombinedOutput()
	body, readErr := os.ReadFile(receipt)
	if readErr != nil {
		if runErr != nil {
			return nil, fmt.Errorf("无法完成安装：%w\n%s", runErr, output)
		}
		return nil, readErr
	}
	if *resultFile != "" {
		if err := os.WriteFile(*resultFile, body, 0600); err != nil {
			return nil, err
		}
	}
	if runErr != nil {
		var result struct {
			Program struct{ Message string }
		}
		if json.Unmarshal(body, &result) == nil && result.Program.Message != "" {
			return body, errors.New(result.Program.Message)
		}
	}
	return body, runErr
}

func message(text string, kind uintptr) {
	value, _ := syscall.UTF16PtrFromString(text)
	title, _ := syscall.UTF16PtrFromString("Skillto.ai Studio 安装")
	box := syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")
	box.Call(0, uintptr(unsafe.Pointer(value)), uintptr(unsafe.Pointer(title)), kind)
}

func main() {
	body, err := run()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		if len(os.Args) == 1 {
			message(err.Error(), 0x10)
		}
		os.Exit(1)
	}
	if len(os.Args) == 1 {
		var result struct {
			LaunchEntry   string
			LaunchCommand string
			Skills        struct{ Status string }
			Window        struct{ Status string }
		}
		if json.Unmarshal(body, &result) == nil {
			if result.Window.Status != "opened" {
				message("工作台已安装。请打开以下入口：\n"+result.LaunchEntry+"\n\n"+result.LaunchCommand, 0x40)
			} else if result.Skills.Status == "needs-attention" {
				message("工作台已打开。已有 Skills 需要核对后再更新。", 0x40)
			}
		}
	} else {
		os.Stdout.Write(body)
	}
}
