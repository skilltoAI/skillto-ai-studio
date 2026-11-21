//go:build windows

// SkillToTable starts the configured local report server and opens its browser UI.
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

type config struct {
	PythonExecutable string `json:"pythonExecutable"`
	ServiceScript    string `json:"serviceScript"`
	WorkingDirectory string `json:"workingDirectory"`
	DataRoot         string `json:"dataRoot"`
	URL              string `json:"url"`
	BridgeScript     string `json:"bridgeScript"`
}
type receipt struct {
	Action               string `json:"action"`
	URL                  string `json:"url,omitempty"`
	ServerPID            int    `json:"serverPid,omitempty"`
	BrowserOpenRequested bool   `json:"browserOpenRequested"`
	Error                string `json:"error,omitempty"`
	LogPath              string `json:"logPath"`
}
type health struct {
	Service       string `json:"service"`
	DataRoot      string `json:"dataRoot"`
	PID           int    `json:"pid"`
	ShutdownEvent string `json:"shutdownEvent"`
}

var (
	kernel32     = syscall.NewLazyDLL("kernel32.dll")
	createMutex  = kernel32.NewProc("CreateMutexW")
	waitObject   = kernel32.NewProc("WaitForSingleObject")
	releaseMutex = kernel32.NewProc("ReleaseMutex")
	shellExecute = syscall.NewLazyDLL("shell32.dll").NewProc("ShellExecuteW")
	messageBox   = syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")
	ole32        = syscall.NewLazyDLL("ole32.dll")
	client       = &http.Client{Timeout: 1200 * time.Millisecond, Transport: &http.Transport{Proxy: nil, DisableKeepAlives: true}, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }}
)

func wide(s string) *uint16     { p, _ := syscall.UTF16PtrFromString(s); return p }
func samePath(a, b string) bool { return strings.EqualFold(filepath.Clean(a), filepath.Clean(b)) }
// Accept the old wire identity during a staged client/service upgrade.
func isTableService(name string) bool {
	return name == "skillto-ai-studio-table" || name == "skillto-int-table"
}
func readConfig(path string) (config, string, error) {
	var c config
	abs, err := filepath.Abs(path)
	if err != nil {
		return c, "", err
	}
	b, err := os.ReadFile(abs)
	if err != nil {
		return c, "", fmt.Errorf("无法读取启动配置 %s: %w", abs, err)
	}
	b = bytes.TrimPrefix(b, []byte{0xef, 0xbb, 0xbf})
	if err = json.Unmarshal(b, &c); err != nil {
		return c, "", fmt.Errorf("启动配置格式错误: %w", err)
	}
	if c.URL == "" {
		c.URL = "http://127.0.0.1:8880/"
	}
	u, err := url.Parse(c.URL)
	if err != nil || u.Scheme != "http" || u.Hostname() != "127.0.0.1" || u.Port() == "" || u.User != nil || u.Path != "/" || u.RawQuery != "" || u.Fragment != "" {
		return c, "", errors.New("配置 URL 必须为 http://127.0.0.1:端口/；默认端口 8880")
	}
	if c.DataRoot == "" || !filepath.IsAbs(c.DataRoot) {
		return c, "", errors.New("dataRoot 必须是本地报表目录的绝对路径")
	}
	if c.BridgeScript == "" {
		c.BridgeScript = filepath.Join(filepath.Dir(abs), "scripts", "launcher_service.py")
	}
	return c, abs, nil
}
func configPath(override string) string {
	if override != "" {
		return override
	}
	exe, _ := os.Executable()
	adjacent := filepath.Join(filepath.Dir(exe), "launcher.local.json")
	if _, err := os.Stat(adjacent); err == nil {
		return adjacent
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".codex", "skills", "skillto-ai-studio-table", "launcher.local.json")
}
func get(path string) ([]byte, int, error) {
	resp, err := client.Get(path)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	b, err := io.ReadAll(io.LimitReader(resp.Body, 1024*1024))
	return b, resp.StatusCode, err
}
func probe(c config) (bool, int, error) {
	b, status, err := get(c.URL + "api/launcher-health")
	if err != nil {
		return false, 0, nil
	}
	if status == 200 {
		var h health
		if json.Unmarshal(b, &h) == nil && isTableService(h.Service) {
			if !samePath(h.DataRoot, c.DataRoot) {
				return false, 0, fmt.Errorf("此端口已有报表服务，但数据目录不同：%s", h.DataRoot)
			}
			return true, h.PID, nil
		}
	}
	// Compatibility with a table server that predates the launcher health endpoint.
	b, status, err = get(c.URL + "api/catalog")
	if err != nil || status != 200 {
		return false, 0, nil
	}
	var catalog struct {
		Version        int             `json:"version"`
		KnowledgeBases json.RawMessage `json:"knowledgeBases"`
	}
	if json.Unmarshal(b, &catalog) != nil || catalog.Version != 2 || len(catalog.KnowledgeBases) == 0 || catalog.KnowledgeBases[0] != '[' {
		return false, 0, nil
	}
	html, status, err := get(c.URL)
	if err == nil && status == 200 && bytes.Contains(html, []byte("/schema-controls.js")) && bytes.Contains(html, []byte("/research-adapter.js")) {
		log.Print("Reusing legacy local table service; it has no launcher health endpoint")
		return true, 0, nil
	}
	return false, 0, nil
}
func occupied(c config) bool {
	u, _ := url.Parse(c.URL)
	conn, err := net.DialTimeout("tcp", u.Host, 400*time.Millisecond)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}
func lock(port string) (func(), error) {
	// A Windows mutex belongs to an OS thread, not a Go goroutine.
	runtime.LockOSThread()
	h, _, err := createMutex.Call(0, 0, uintptr(unsafe.Pointer(wide("Local\\SkillToIntTable-"+port))))
	if h == 0 {
		runtime.UnlockOSThread()
		return nil, fmt.Errorf("创建启动锁失败: %v", err)
	}
	result, _, _ := waitObject.Call(h, 45000)
	if result != 0 && result != 0x80 {
		syscall.CloseHandle(syscall.Handle(h))
		runtime.UnlockOSThread()
		return nil, errors.New("另一个启动器仍在启动服务，请稍后重试")
	}
	return func() { releaseMutex.Call(h); syscall.CloseHandle(syscall.Handle(h)); runtime.UnlockOSThread() }, nil
}
func validateFiles(c config) error {
	for _, p := range []string{c.PythonExecutable, c.ServiceScript, c.BridgeScript} {
		if !filepath.IsAbs(p) {
			return fmt.Errorf("配置必须使用绝对文件路径: %s", p)
		}
		info, err := os.Stat(p)
		if err != nil || info.IsDir() {
			return fmt.Errorf("启动文件不存在: %s", p)
		}
	}
	for _, p := range []string{c.WorkingDirectory, c.DataRoot} {
		info, err := os.Stat(p)
		if err != nil || !info.IsDir() {
			return fmt.Errorf("目录不存在: %s", p)
		}
	}
	return nil
}
func start(c config, path string, r *receipt) error {
	u, _ := url.Parse(c.URL)
	unlock, err := lock(u.Port())
	if err != nil {
		return err
	}
	defer unlock()
	ready, pid, err := probe(c)
	if err != nil {
		return err
	}
	if ready {
		r.Action = "reused"
		r.ServerPID = pid
		return nil
	}
	if occupied(c) {
		return fmt.Errorf("端口 %s 已被其他程序占用，未启动报表服务。请关闭占用程序或修改 launcher.local.json", u.Port())
	}
	if err = validateFiles(c); err != nil {
		return err
	}
	cmd := exec.Command(c.PythonExecutable, "-X", "utf8", c.BridgeScript, "--config", path)
	cmd.Dir = c.WorkingDirectory
	for _, e := range os.Environ() {
		k, _, _ := strings.Cut(e, "=")
		if !strings.EqualFold(k, "SKILLTO_TABLE_API_URL") && !strings.EqualFold(k, "SKILLTO_TABLE_API_KEY_FILE") && !strings.EqualFold(k, "SKILLTO_TABLE_ROOT") {
			cmd.Env = append(cmd.Env, e)
		}
	}
	cmd.Env = append(cmd.Env, "SKILLTO_TABLE_ROOT="+c.DataRoot, "PYTHONUTF8=1")
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000 | 0x00000200}
	serviceLog, err := os.OpenFile(filepath.Join(filepath.Dir(r.LogPath), "service.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	cmd.Stdout = serviceLog
	cmd.Stderr = serviceLog
	if err = cmd.Start(); err != nil {
		serviceLog.Close()
		return fmt.Errorf("无法启动 Python 报表服务: %w", err)
	}
	serviceLog.Close()
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	deadline := time.Now().Add(35 * time.Second)
	for time.Now().Before(deadline) {
		ready, pid, err = probe(c)
		if err != nil {
			_ = cmd.Process.Kill()
			return err
		}
		if ready {
			r.Action = "started"
			r.ServerPID = pid
			return nil
		}
		select {
		case exitErr := <-done:
			return fmt.Errorf("报表服务启动后退出 (%v)，请查看 service.log", exitErr)
		default:
		}
		time.Sleep(250 * time.Millisecond)
	}
	_ = cmd.Process.Kill()
	return errors.New("等待报表服务就绪超时，已结束本次启动的进程。请查看 service.log")
}
func openBrowser(address string) error {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	hr, _, _ := ole32.NewProc("CoInitializeEx").Call(0, 2)
	if int32(hr) >= 0 {
		defer ole32.NewProc("CoUninitialize").Call()
	}
	result, _, _ := shellExecute.Call(0, uintptr(unsafe.Pointer(wide("open"))), uintptr(unsafe.Pointer(wide(address))), 0, 0, 1)
	if result <= 32 {
		return fmt.Errorf("服务已启动，但无法打开默认浏览器 (Windows 错误 %d)。请手动打开 %s", result, address)
	}
	return nil
}
func run() int {
	flags := flag.NewFlagSet("SkillToTable", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	cfg := flags.String("config", "", "Configuration file")
	noBrowser := flags.Bool("no-browser", false, "Start without opening browser (one-shot diagnostic)")
	headless := flags.Bool("headless", false, "Run once without taskbar window")
	stopRequested := flags.Bool("stop", false, "Stop the local report service")
	quiet := flags.Bool("quiet-errors", false, "Log errors without a dialog")
	resultFile := flags.String("result-file", "", "Write a diagnostic receipt")
	parseErr := flags.Parse(os.Args[1:])
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	dir := filepath.Join(base, "SkillToTable", "logs")
	r := receipt{Action: "error", LogPath: filepath.Join(dir, "launcher.log")}
	err := os.MkdirAll(dir, 0700)
	if err == nil {
		var f *os.File
		f, err = os.OpenFile(r.LogPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
		if err == nil {
			defer f.Close()
			log.SetOutput(f)
		}
	}
	if err == nil {
		err = parseErr
	}
	if err == nil {
		var c config
		var path string
		c, path, err = readConfig(configPath(*cfg))
		r.URL = c.URL
		if err == nil {
			log.Printf("Launching %s using %s", c.URL, path)
			if *stopRequested {
				err = stop(c, &r)
			} else if !*headless && !*noBrowser {
				err = controlWindow(c, path, &r, *resultFile)
			} else {
				err = start(c, path, &r)
			}
		}
		if err == nil && !*noBrowser && *headless && !*stopRequested {
			err = openBrowser(c.URL)
			r.BrowserOpenRequested = err == nil
		}
	}
	if err != nil {
		r.Action = "error"
		r.Error = err.Error()
		log.Print(r.Error)
	} else {
		log.Printf("%s service pid=%d browser=%t", r.Action, r.ServerPID, r.BrowserOpenRequested)
	}
	if *resultFile != "" {
		b, _ := json.MarshalIndent(r, "", "  ")
		if e := os.WriteFile(*resultFile, b, 0600); e != nil {
			log.Printf("Cannot write receipt: %v", e)
		}
	}
	if err != nil {
		if !*quiet {
			messageBox.Call(0, uintptr(unsafe.Pointer(wide(r.Error+"\n\n日志："+r.LogPath))), uintptr(unsafe.Pointer(wide("Skillto-AI-Studio 启动失败"))), 0x10)
		}
		return 1
	}
	return 0
}
func main() { os.Exit(run()) }
