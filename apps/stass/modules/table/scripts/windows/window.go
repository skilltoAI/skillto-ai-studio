//go:build windows

package main

import (
	"context"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/windows"
	ui "github.com/wailsapp/wails/v2/pkg/runtime"
)

//go:embed ui
var assets embed.FS

var errBeamNotIncluded = errors.New("发行清单未包含 Beam")

type ViewState struct {
	Phase   string `json:"phase"`
	Running bool   `json:"running"`
	URL     string `json:"url"`
	PID     int    `json:"pid"`
	Uptime  int    `json:"uptime"`
	Version string `json:"version"`
	Error   string `json:"error"`
}

type Launcher struct {
	cfg                 config
	ctx                 context.Context
	mu                  sync.Mutex
	state               ViewState
	current             receipt
	resultFile          string
	closing, allowClose bool
	closeRequested      bool
	beamMu              sync.Mutex
	lastBeam            time.Time
}

func controlWindow(c config, _ string, r *receipt, resultFile string) error {
	page, err := fs.Sub(assets, "ui")
	if err != nil {
		return err
	}
	a := &Launcher{cfg: c, state: ViewState{Phase: "starting", URL: c.URL, Version: c.ActiveVersion}, current: *r, resultFile: resultFile}
	userData := filepath.Join(filepath.Dir(filepath.Dir(c.ConfigFile)), "launcher-webview")
	err = wails.Run(&options.App{
		Title: "SKillto.ai 个人工作台", Width: 820, Height: 540, MinWidth: 420, MinHeight: 320, Frameless: true,
		BackgroundColour: options.NewRGB(255, 255, 255),
		AssetServer:      &assetserver.Options{Assets: page},
		Windows:          &windows.Options{WebviewUserDataPath: userData, DisablePinchZoom: true},
		Bind:             []interface{}{a},
		OnDomReady: func(ctx context.Context) {
			a.mu.Lock()
			first := a.ctx == nil
			a.ctx = ctx
			a.mu.Unlock()
			if first {
				go a.changeService(true, true)
				go a.poll(ctx)
			}
		},
		OnBeforeClose: a.beforeClose,
		SingleInstanceLock: &options.SingleInstanceLock{
			UniqueId: "Skillto-Studio-" + c.InstanceID,
			OnSecondInstanceLaunch: func(options.SecondInstanceData) {
				a.mu.Lock()
				ctx := a.ctx
				a.mu.Unlock()
				if ctx != nil {
					ui.WindowUnminimise(ctx)
					ui.WindowShow(ctx)
				}
			},
		},
	})
	a.mu.Lock()
	defer a.mu.Unlock()
	*r = a.current
	if a.ctx == nil && err == nil {
		r.Action = "focused"
		r.Error = ""
	}
	return err
}

func (a *Launcher) State() ViewState {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.state
}

func (a *Launcher) publish() {
	if a.ctx != nil {
		ui.EventsEmit(a.ctx, "launcher:state", a.state)
	}
	if a.resultFile != "" {
		b, _ := json.MarshalIndent(a.current, "", "  ")
		if err := os.WriteFile(a.resultFile, b, 0600); err != nil {
			log.Printf("写入启动回执失败: %v", err)
		}
	}
}

func (a *Launcher) refresh() error {
	c, _, err := readConfig(a.cfg.ConfigFile)
	if err != nil {
		return err
	}
	h, err := readHealth(c)
	if err != nil {
		return err
	}
	a.state.URL = c.URL
	a.state.Version = c.ActiveVersion
	a.state.Running = h.PID > 0
	a.state.PID = h.PID
	a.state.Uptime = h.Uptime
	if h.Version != "" {
		a.state.Version = h.Version
	}
	a.current.URL = c.URL
	a.current.ServerPID = h.PID
	return nil
}

func (a *Launcher) settle(err error) {
	a.state.Error = ""
	a.state.Phase = "stopped"
	if a.state.Running {
		a.state.Phase = "running"
	}
	if err != nil {
		a.state.Phase = "error"
		a.state.Error = err.Error()
		log.Printf("启动器操作未完成: %v", err)
	}
	a.publish()
}

func (a *Launcher) poll(ctx context.Context) {
	ticker := time.NewTicker(4 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			a.mu.Lock()
			if !a.closing && a.state.Phase != "starting" && a.state.Phase != "stopping" {
				before := a.state
				err := a.refresh()
				if err != nil {
					a.state.Running = false
					a.state.PID = 0
					a.state.Uptime = 0
					a.settle(err)
				} else if a.state != before || (before.Phase == "error" && before.Error == "此地址不是选定的STASS实例，未接管其他程序") {
					if before.Phase == "error" && before.Running == a.state.Running && before.Error != "此地址不是选定的STASS实例，未接管其他程序" {
						a.publish()
					} else {
						a.settle(nil)
					}
				}
			}
			a.mu.Unlock()
		}
	}
}

func (a *Launcher) Start() { a.changeService(true, false) }
func (a *Launcher) Stop()  { a.changeService(false, false) }

func (a *Launcher) changeService(starting, initial bool) {
	a.mu.Lock()
	if a.closing || (!initial && (a.state.Phase == "starting" || a.state.Phase == "stopping")) || (starting == a.state.Running && !initial) {
		a.mu.Unlock()
		return
	}
	a.state.Phase = "stopping"
	if starting {
		a.state.Phase = "starting"
	}
	a.state.Error = ""
	r := a.current
	r.Error = ""
	a.publish()
	a.mu.Unlock()
	var err error
	if starting {
		err = start(a.cfg, a.cfg.ConfigFile, &r)
	} else {
		err = stop(a.cfg, &r)
	}
	a.mu.Lock()
	a.current = r
	if err == nil {
		a.state.Running = starting
		a.state.PID = r.ServerPID
	}
	refreshErr := a.refresh()
	if err == nil {
		err = refreshErr
	}
	if err != nil {
		a.current.Action = "error"
		a.current.Error = err.Error()
	}
	a.settle(err)
	closeRequested := a.closeRequested
	a.closeRequested = false
	ctx := a.ctx
	open := initial && !closeRequested && !a.closing && err == nil
	a.mu.Unlock()
	if closeRequested && ctx != nil {
		ui.Quit(ctx)
		return
	}
	if open {
		if err := a.OpenWorkbench(); err != nil {
			a.mu.Lock()
			a.settle(err)
			a.mu.Unlock()
		}
	}
}

func (a *Launcher) beforeClose(context.Context) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.allowClose {
		return false
	}
	if a.closing {
		return true
	}
	if a.state.Phase == "starting" || a.state.Phase == "stopping" {
		a.closeRequested = true
		return true
	}
	a.closing = true
	a.state.Phase = "stopping"
	a.publish()
	r := a.current
	ctx := a.ctx
	go func() {
		// Always let the shared runtime manager check ownership and live state.
		err := stop(a.cfg, &r)
		a.mu.Lock()
		if err != nil {
			a.closing = false
			_ = a.refresh()
			a.settle(err)
			a.mu.Unlock()
			return
		}
		a.current = r
		a.state.Running = false
		a.state.PID = 0
		a.settle(nil)
		a.allowClose = true
		a.mu.Unlock()
		ui.Quit(ctx)
	}()
	return true
}

func (a *Launcher) runningConfig() (config, error) {
	c, _, err := readConfig(a.cfg.ConfigFile)
	if err != nil {
		return c, err
	}
	h, err := readHealth(c)
	if err == nil && h.PID <= 0 {
		err = errors.New("请先启动工作台服务")
	}
	return c, err
}
func (a *Launcher) OpenWorkbench() error {
	c, err := a.runningConfig()
	if err != nil {
		return err
	}
	err = openBrowser(c.URL)
	a.mu.Lock()
	defer a.mu.Unlock()
	a.current.BrowserOpenRequested = err == nil
	a.publish()
	return err
}
func (a *Launcher) OpenBrowserUsers() error {
	c, err := a.runningConfig()
	if err != nil {
		return err
	}
	return openBrowser(c.URL + "browser-users")
}
func (a *Launcher) PairCode() (PairCode, error) {
	c, err := a.runningConfig()
	if err != nil {
		return PairCode{}, err
	}
	return fetchPairCode(c)
}

// WorkPreferences uses the packaged interpreter while the web service is stopped.
func (a *Launcher) WorkPreferences(request string) (string, error) {
	if len(request) > 16384 {
		return "", errors.New("组件选择过长")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	c := a.cfg
	cmd := exec.CommandContext(ctx, c.PythonExecutable, "-B", "-X", "utf8", filepath.Join(c.Program.Directory, "work_profiles.py"))
	cmd.Dir = c.Program.Directory
	if _, configured := os.LookupEnv("STASS_PREFERENCES_DIR"); !configured && c.ConfigFile != "" {
		cmd.Env = append(os.Environ(), "STASS_PREFERENCES_DIR="+filepath.Join(filepath.Dir(filepath.Dir(c.ConfigFile)), "preferences"))
	}
	cmd.Stdin = strings.NewReader(request)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	data, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("工作偏好：%s (%w)", data, err)
	}
	return string(data), nil
}

func (a *Launcher) OpenBeam() error {
	a.beamMu.Lock()
	defer a.beamMu.Unlock()
	if time.Since(a.lastBeam) < 1500*time.Millisecond {
		return nil
	}
	c, _, err := readConfig(a.cfg.ConfigFile)
	if err != nil {
		return err
	}
	root := filepath.Dir(c.Program.Directory)
	dir := filepath.Join(root, "beam")
	binary := filepath.Join(dir, "SkilltoBeam.exe")
	if err := verifyBeam(root, c.Release.ManifestSHA256); err != nil {
		if errors.Is(err, errBeamNotIncluded) {
			return fmt.Errorf("当前选用的工作台版本 %s 未包含 3D 录屏。请切换到包含 Beam 的完整发行包。", c.ActiveVersion)
		}
		log.Printf("Beam integrity: %v", err)
		return errors.New("3D 录屏组件未通过发行清单校验，请使用同一版本的完整安装包修复")
	}
	for _, name := range []string{binary, filepath.Join(dir, "resources", "app.asar"), filepath.Join(dir, "icudtl.dat")} {
		info, err := os.Stat(name)
		if err != nil || !info.Mode().IsRegular() || info.Size() == 0 {
			return errors.New("3D 录屏组件缺失或不完整，请重新安装工作台发行包")
		}
	}
	cmd := exec.Command(binary)
	cmd.Dir = dir
	if err := cmd.Start(); err != nil {
		return errors.New("无法打开 3D 录屏：" + err.Error())
	}
	a.lastBeam = time.Now()
	go func() {
		if err := cmd.Wait(); err != nil {
			log.Printf("Beam: %v", err)
		}
	}()
	return nil
}

func verifyBeam(root, expected string) error {
	if expected == "" {
		return errBeamNotIncluded
	}
	data, err := os.ReadFile(filepath.Join(root, "release.json"))
	if err != nil {
		return err
	}
	if fmt.Sprintf("%x", sha256.Sum256(data)) != expected {
		return errors.New("发行清单摘要不符")
	}
	var manifest struct {
		Files map[string]string `json:"files"`
	}
	if err := json.Unmarshal(data, &manifest); err != nil {
		return err
	}
	files := map[string]string{}
	for path, digest := range manifest.Files {
		if strings.HasPrefix(path, "beam/") {
			files[path] = digest
		}
	}
	if len(files) == 0 {
		return errBeamNotIncluded
	}
	if err := filepath.WalkDir(filepath.Join(root, "beam"), func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		name, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		name = filepath.ToSlash(name)
		digest, ok := files[name]
		if !ok || !entry.Type().IsRegular() {
			return fmt.Errorf("发行清单未授权文件 %s", name)
		}
		f, err := os.Open(path)
		if err != nil {
			return err
		}
		defer f.Close()
		hash := sha256.New()
		if _, err = io.Copy(hash, f); err != nil {
			return err
		}
		if hex.EncodeToString(hash.Sum(nil)) != digest {
			return fmt.Errorf("文件摘要不符 %s", name)
		}
		delete(files, name)
		return nil
	}); err != nil {
		return err
	}
	if len(files) != 0 {
		return errors.New("发行清单中的 Beam 文件缺失")
	}
	return nil
}
