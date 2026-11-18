//go:build windows

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/url"
	"os"
	"runtime"
	"syscall"
	"time"
	"unsafe"
)

const (
	wmClose    = 0x0010
	wmDestroy  = 0x0002
	wmCommand  = 0x0111
	wmTimer    = 0x0113
	wmDone     = 0x8001
	wmFocusApp = 0x8002
	idStart    = 1001
	idStop     = 1002
	idOpen     = 1003
	idBrowsers = 1004
	idPair     = 1005
)

var (
	user32         = syscall.NewLazyDLL("user32.dll")
	gdi32          = syscall.NewLazyDLL("gdi32.dll")
	createWindow   = user32.NewProc("CreateWindowExW")
	sendMessage    = user32.NewProc("SendMessageW")
	postMessage    = user32.NewProc("PostMessageW")
	setText        = user32.NewProc("SetWindowTextW")
	enableWindow   = user32.NewProc("EnableWindow")
	activeUI       *controller
	windowCallback = syscall.NewCallback(windowProc)
)

type windowClass struct {
	Size, Style                        uint32
	Procedure                          uintptr
	ClassExtra, WindowExtra            int32
	Instance, Icon, Cursor, Background uintptr
	MenuName, ClassName                *uint16
	SmallIcon                          uintptr
}
type point struct{ X, Y int32 }
type nativeMessage struct {
	Window         uintptr
	Message        uint32
	WParam, LParam uintptr
	Time           uint32
	Point          point
	Private        uint32
}
type rectangle struct{ Left, Top, Right, Bottom int32 }
type jobResult struct {
	operation string
	result    receipt
	err       error
	ready     bool
	open      bool
}
type controller struct {
	cfg                                                       config
	configPath                                                string
	hwnd, status, detail, startButton, stopButton, openButton uintptr
	font, titleFont                                           uintptr
	busy, running, closing                                    bool
	current                                                   receipt
	resultFile                                                string
	results                                                   chan jobResult
}

func controlWindow(c config, path string, r *receipt, resultFile string) error {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	u, _ := url.Parse(c.URL)
	className := "SkillToTableControl" + u.Port()
	// Keep one controller per port, including when the EXE is launched from a pin.
	gate, _, gateErr := createMutex.Call(0, 0, uintptr(unsafe.Pointer(wide("Local\\SkillToTableUI-"+u.Port()))))
	if gate == 0 {
		return fmt.Errorf("创建任务栏控制器失败: %v", gateErr)
	}
	defer syscall.CloseHandle(syscall.Handle(gate))
	if gateErr == syscall.Errno(183) {
		for i := 0; i < 30; i++ {
			existing, _, _ := user32.NewProc("FindWindowW").Call(uintptr(unsafe.Pointer(wide(className))), 0)
			if existing != 0 {
				user32.NewProc("ShowWindow").Call(existing, 9)
				user32.NewProc("SetForegroundWindow").Call(existing)
				postMessage.Call(existing, wmFocusApp, 0, 0)
				r.Action = "focused"
				return nil
			}
			time.Sleep(50 * time.Millisecond)
		}
		return fmt.Errorf("任务栏控制窗口仍在启动，请稍后重试")
	}
	app := &controller{cfg: c, configPath: path, current: *r, resultFile: resultFile, results: make(chan jobResult, 2)}
	activeUI = app
	defer func() { activeUI = nil }()
	instance, _, _ := kernel32.NewProc("GetModuleHandleW").Call(0)
	largeIcon, _, _ := user32.NewProc("LoadImageW").Call(instance, uintptr(unsafe.Pointer(wide("APP"))), 1, 48, 48, 0x8000)
	smallIcon, _, _ := user32.NewProc("LoadImageW").Call(instance, uintptr(unsafe.Pointer(wide("APP"))), 1, 16, 16, 0x8000)
	cursor, _, _ := user32.NewProc("LoadCursorW").Call(0, 32512)
	cls := windowClass{Procedure: windowCallback, Instance: instance, Icon: largeIcon, SmallIcon: smallIcon, Cursor: cursor, Background: 6, ClassName: wide(className)}
	cls.Size = uint32(unsafe.Sizeof(cls))
	atom, _, registerErr := user32.NewProc("RegisterClassExW").Call(uintptr(unsafe.Pointer(&cls)))
	if atom == 0 {
		return fmt.Errorf("注册任务栏窗口失败: %v", registerErr)
	}
	defer user32.NewProc("UnregisterClassW").Call(uintptr(unsafe.Pointer(wide(className))), instance)
	const style = 0x00CA0000 // caption, system menu, minimize button, fixed frame
	rect := rectangle{Right: 584, Bottom: 340}
	user32.NewProc("AdjustWindowRectEx").Call(uintptr(unsafe.Pointer(&rect)), style, 0, 0x40000)
	width, height := uintptr(rect.Right-rect.Left), uintptr(rect.Bottom-rect.Top)
	screenW, _, _ := user32.NewProc("GetSystemMetrics").Call(0)
	screenH, _, _ := user32.NewProc("GetSystemMetrics").Call(1)
	hwnd, _, windowErr := createWindow.Call(0x40000, uintptr(unsafe.Pointer(wide(className))), uintptr(unsafe.Pointer(wide("SKillto.ai 个人工作台"))), style, (screenW-width)/2, (screenH-height)/2, width, height, 0, 0, instance, 0)
	if hwnd == 0 {
		return fmt.Errorf("创建任务栏窗口失败: %v", windowErr)
	}
	app.hwnd = hwnd
	app.font, _, _ = gdi32.NewProc("CreateFontW").Call(^uintptr(16), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, uintptr(unsafe.Pointer(wide("Microsoft YaHei UI"))))
	app.titleFont, _, _ = gdi32.NewProc("CreateFontW").Call(^uintptr(22), 0, 0, 0, 600, 0, 0, 0, 1, 0, 0, 5, 0, uintptr(unsafe.Pointer(wide("Microsoft YaHei UI"))))
	defer gdi32.NewProc("DeleteObject").Call(app.font)
	defer gdi32.NewProc("DeleteObject").Call(app.titleFont)
	child := func(class, text string, x, y, w, h, id int, extra uintptr) uintptr {
		control, _, _ := createWindow.Call(0, uintptr(unsafe.Pointer(wide(class))), uintptr(unsafe.Pointer(wide(text))), 0x50000000|extra, uintptr(x), uintptr(y), uintptr(w), uintptr(h), hwnd, uintptr(id), instance, 0)
		sendMessage.Call(control, 0x0030, app.font, 1)
		return control
	}
	logo := child("STATIC", "", 25, 24, 48, 48, 0, 3)
	sendMessage.Call(logo, 0x0170, largeIcon, 0)
	title := child("STATIC", "SKillto.ai 个人工作台", 91, 26, 450, 34, 0, 0)
	sendMessage.Call(title, 0x0030, app.titleFont, 1)
	child("STATIC", c.URL, 92, 62, 450, 25, 0, 0)
	app.status = child("STATIC", "正在启动服务…", 27, 105, 532, 28, 0, 0)
	app.detail = child("STATIC", "服务就绪后将打开浏览器", 27, 139, 532, 28, 0, 0)
	app.startButton = child("BUTTON", "启动服务", 27, 185, 162, 40, idStart, 0x10000)
	app.stopButton = child("BUTTON", "关闭服务", 210, 185, 162, 40, idStop, 0x10000)
	app.openButton = child("BUTTON", "打开工作台", 393, 185, 162, 40, idOpen, 0x10001)
	child("BUTTON", "浏览器用户", 27, 238, 350, 40, idBrowsers, 0x10000)
	child("BUTTON", "获取网页配对码", 393, 238, 162, 40, idPair, 0x10000)
	child("STATIC", "首次使用请获取网页配对码；最小化后服务继续运行。", 27, 300, 535, 25, 0, 0)
	sendMessage.Call(hwnd, 0x0080, 0, smallIcon)
	sendMessage.Call(hwnd, 0x0080, 1, largeIcon)
	app.buttons()
	user32.NewProc("ShowWindow").Call(hwnd, 1)
	user32.NewProc("UpdateWindow").Call(hwnd)
	user32.NewProc("SetTimer").Call(hwnd, 1, 4000, 0)
	app.perform("start", true)
	var msg nativeMessage
	for {
		got, _, getErr := user32.NewProc("GetMessageW").Call(uintptr(unsafe.Pointer(&msg)), 0, 0, 0)
		if int32(got) == -1 {
			return fmt.Errorf("任务栏消息处理失败: %v", getErr)
		}
		if got == 0 {
			break
		}
		dialog, _, _ := user32.NewProc("IsDialogMessageW").Call(hwnd, uintptr(unsafe.Pointer(&msg)))
		if dialog == 0 {
			user32.NewProc("TranslateMessage").Call(uintptr(unsafe.Pointer(&msg)))
			user32.NewProc("DispatchMessageW").Call(uintptr(unsafe.Pointer(&msg)))
		}
	}
	*r = app.current
	return nil
}
func (a *controller) buttons() {
	values := []struct {
		handle  uintptr
		enabled bool
	}{{a.startButton, !a.busy && !a.running && !a.closing}, {a.stopButton, !a.busy && a.running && !a.closing}, {a.openButton, !a.busy && a.running && !a.closing}}
	for _, b := range values {
		var on uintptr
		if b.enabled {
			on = 1
		}
		enableWindow.Call(b.handle, on)
	}
}
func text(handle uintptr, value string) { setText.Call(handle, uintptr(unsafe.Pointer(wide(value)))) }
func (a *controller) display() {
	if a.running {
		text(a.status, "服务正在运行")
		text(a.detail, fmt.Sprintf("端口 %s  ·  服务进程 %d", portOf(a.cfg.URL), a.current.ServerPID))
		text(a.hwnd, "Skillto-AI-Studio · 运行中")
	} else {
		text(a.status, "服务已关闭")
		text(a.detail, "点击“启动服务”重新启动，报表数据保留在本地")
		text(a.hwnd, "Skillto-AI-Studio · 已关闭")
	}
	a.buttons()
}
func portOf(address string) string { u, _ := url.Parse(address); return u.Port() }
func (a *controller) saveReceipt() {
	if a.resultFile != "" {
		b, _ := json.MarshalIndent(a.current, "", "  ")
		if err := os.WriteFile(a.resultFile, b, 0600); err != nil {
			log.Print(err)
		}
	}
}
func (a *controller) perform(operation string, openAfter bool) {
	if a.busy {
		return
	}
	a.busy = true
	if operation != "refresh" {
		a.buttons()
		if operation == "start" {
			text(a.status, "正在启动服务…")
			text(a.detail, "请稍候，服务就绪后即可使用")
		}
		if operation == "stop" {
			text(a.status, "正在关闭服务…")
			text(a.detail, "正在等待当前请求完成")
		}
	}
	r := a.current
	go func() {
		result := jobResult{operation: operation, result: r, open: openAfter}
		switch operation {
		case "start":
			result.err = start(a.cfg, a.configPath, &result.result)
			result.ready = result.err == nil
		case "stop":
			result.err = stop(a.cfg, &result.result)
		case "open":
			result.err = openBrowser(a.cfg.URL)
			result.result.BrowserOpenRequested = result.err == nil
			result.ready = true
		case "pair":
			result.err = showPairCode(a.cfg, a.hwnd)
		case "browsers":
			result.err = openBrowser(a.cfg.URL + "browser-users")
		case "refresh":
			result.ready, result.result.ServerPID, result.err = probe(a.cfg)
		}
		a.results <- result
		postMessage.Call(a.hwnd, wmDone, 0, 0)
	}()
}
func (a *controller) completed() {
	result := <-a.results
	a.busy = false
	switch result.operation {
	case "start":
		if result.err == nil {
			a.current = result.result
			a.running = true
		}
	case "stop":
		if result.err == nil {
			a.current = result.result
			a.running = false
		}
	case "open":
		a.current.BrowserOpenRequested = result.err == nil
	case "refresh":
		if result.err == nil {
			a.running = result.ready
			a.current.ServerPID = result.result.ServerPID
		}
	}
	a.saveReceipt()
	a.display()
	if result.err != nil {
		log.Printf("Taskbar %s: %v", result.operation, result.err)
		text(a.status, "操作未完成")
		text(a.detail, result.err.Error())
		if result.operation == "stop" {
			a.closing = false
			a.buttons()
		}
	}
	if a.closing {
		if a.running {
			a.perform("stop", false)
		} else {
			user32.NewProc("DestroyWindow").Call(a.hwnd)
		}
		return
	}
	if result.operation == "start" && result.err == nil && result.open {
		a.perform("open", false)
	}
}
func windowProc(hwnd uintptr, message uint32, wParam, lParam uintptr) uintptr {
	a := activeUI
	if a != nil {
		switch message {
		case wmCommand:
			if a.busy || a.closing {
				return 0
			}
			switch wParam & 0xffff {
			case idStart:
				a.perform("start", false)
			case idStop:
				a.perform("stop", false)
			case idOpen:
				a.perform("open", false)
			case idPair:
				if a.running {
					a.perform("pair", false)
				}
			case idBrowsers:
				if a.running {
					a.perform("browsers", false)
				}
			}
			return 0
		case wmDone:
			a.completed()
			return 0
		case wmFocusApp:
			user32.NewProc("ShowWindow").Call(hwnd, 9)
			user32.NewProc("SetForegroundWindow").Call(hwnd)
			return 0
		case wmTimer:
			if !a.busy && !a.closing {
				a.perform("refresh", false)
			}
			return 0
		case wmClose:
			a.closing = true
			if !a.busy {
				if a.running {
					a.perform("stop", false)
				} else {
					user32.NewProc("DestroyWindow").Call(hwnd)
				}
			}
			return 0
		case wmDestroy:
			user32.NewProc("KillTimer").Call(hwnd, 1)
			user32.NewProc("PostQuitMessage").Call(0)
			return 0
		}
	}
	result, _, _ := user32.NewProc("DefWindowProcW").Call(hwnd, uintptr(message), wParam, lParam)
	return result
}
