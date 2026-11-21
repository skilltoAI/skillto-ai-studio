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
	ActiveVersion string `json:"activeVersion"`
	InstanceID    string `json:"instanceId"`
	Release       struct {
		ManifestSHA256 string `json:"manifestSha256"`
		Commit         string `json:"commit"`
	} `json:"release"`
	Program struct {
		Directory string `json:"directory"`
		Python    string `json:"python"`
	} `json:"program"`
	ConfigFile       string `json:"-"`
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
	Version        string `json:"version"`
	Uptime         int    `json:"uptimeSeconds"`
	InstanceID     string `json:"instanceId"`
	Service        string `json:"service"`
	DataRoot       string `json:"dataRoot"`
	PID            int    `json:"pid"`
	ShutdownEvent  string `json:"shutdownEvent"`
	ReleaseCommit  string `json:"releaseCommit"`
	ManifestSHA256 string `json:"manifestSha256"`
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

func wide(s string) *uint16 { p, _ := syscall.UTF16PtrFromString(s); return p }
func readConfig(path string) (config, string, error) {
	var c config
	abs, err := filepath.Abs(path)
	if err != nil {
		return c, "", err
	}
	body, err := os.ReadFile(abs)
	if err != nil {
		return c, "", fmt.Errorf("尚未安装共享工作台，请先运行离线安装器: %w", err)
	}
	if err = json.Unmarshal(bytes.TrimPrefix(body, []byte{0xef, 0xbb, 0xbf}), &c); err != nil {
		return c, "", err
	}
	parsed, err := url.Parse(c.URL)
	if err != nil || parsed.Scheme != "http" || parsed.Hostname() != "127.0.0.1" || parsed.Port() == "" || parsed.Path != "/STASS/" || parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" || c.InstanceID == "" {
		return c, "", errors.New("共享实例配置无效，必须使用本机STASS地址和实例ID")
	}
	c.ConfigFile = abs
	c.PythonExecutable = c.Program.Python
	c.WorkingDirectory = c.Program.Directory
	c.ServiceScript = filepath.Join(c.Program.Directory, "service.py")
	c.BridgeScript = filepath.Join(c.Program.Directory, "runtime_control.py")
	return c, abs, nil
}
func configPath(override string) string {
	if override != "" {
		return override
	}
	return filepath.Join(os.Getenv("LOCALAPPDATA"), "Skillto.ai", "Studio", "config", "installation.json")
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
func readHealth(c config) (health, error) {
	var h health
	body, status, err := get(c.URL + "health")
	if err != nil {
		return h, nil
	}
	if status != 200 || json.Unmarshal(body, &h) != nil || h.Service != "STASS" || h.InstanceID != c.InstanceID || h.PID <= 0 {
		return health{}, errors.New("此地址不是选定的STASS实例，未接管其他程序")
	}
	if c.Release.Commit != "" && (h.ReleaseCommit != c.Release.Commit || h.Version != c.ActiveVersion ||
		(h.ManifestSHA256 != "" && h.ManifestSHA256 != c.Release.ManifestSHA256)) {
		return health{}, errors.New("运行服务的发行身份与安装配置不一致")
	}
	return h, nil
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
func manage(c config, operation string, r *receipt) error {
	current, _, err := readConfig(c.ConfigFile)
	if err != nil {
		return err
	}
	if err = validateFiles(current); err != nil {
		return err
	}
	root := filepath.Dir(filepath.Dir(current.ConfigFile))
	cmd := exec.Command(current.PythonExecutable, "-B", "-X", "utf8", current.BridgeScript, operation, "--root", root)
	cmd.Dir = current.WorkingDirectory
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("共享工作台%s未完成: %s", operation, string(output))
	}
	var result struct {
		Action string `json:"action"`
		PID    int    `json:"pid"`
	}
	if err = json.Unmarshal(output, &result); err != nil {
		return fmt.Errorf("管理器返回无效结果: %w", err)
	}
	r.Action = result.Action
	r.ServerPID = result.PID
	r.URL = current.URL
	return nil
}
func start(c config, path string, r *receipt) error { return manage(c, "start", r) }

type PairCode struct {
	Code      string `json:"code"`
	ExpiresIn int    `json:"expiresIn"`
}

func fetchPairCode(current config) (PairCode, error) {
	var result PairCode
	token, err := os.ReadFile(filepath.Join(filepath.Dir(current.ConfigFile), "admin.token"))
	if err != nil {
		return result, errors.New("无法读取本机配对凭据")
	}
	req, err := http.NewRequest("GET", current.URL+"api/v1/pair-code", nil)
	if err != nil {
		return result, err
	}
	req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(string(token)))
	response, err := client.Do(req)
	if err != nil {
		return result, errors.New("无法连接配对接口")
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return result, errors.New("配对接口拒绝请求，请确认本机实例已启动")
	}
	if err = json.NewDecoder(io.LimitReader(response.Body, 4096)).Decode(&result); err != nil || len(result.Code) != 24 || result.ExpiresIn <= 0 {
		return PairCode{}, errors.New("服务返回了无效的配对码")
	}
	return result, nil
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
	dir := filepath.Join(base, "Skillto.ai", "Studio", "logs")
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
