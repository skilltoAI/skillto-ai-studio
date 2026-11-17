//go:build windows

package main

import (
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/url"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

// A per-server Windows event requests graceful shutdown without exposing a web
// shutdown endpoint. Python waits for active HTTP handlers before exiting.
func stop(c config, r *receipt) error {
	u, _ := url.Parse(c.URL)
	unlock, err := lock(u.Port())
	if err != nil {
		return err
	}
	defer unlock()
	if !occupied(c) {
		r.Action = "stopped"
		r.ServerPID = 0
		return nil
	}
	b, status, err := get(c.URL + "api/launcher-health")
	if err != nil || status != 200 {
		return errors.New("此端口没有可管理的本地报表服务，未关闭其他程序")
	}
	var h health
	if json.Unmarshal(b, &h) != nil || h.Service != "skillto-int-table" || !samePath(h.DataRoot, c.DataRoot) || h.PID <= 0 {
		return errors.New("服务标识或数据目录不匹配，未关闭其他程序")
	}
	const prefix = "Local\\SkillToTableShutdown-"
	suffix := strings.TrimPrefix(h.ShutdownEvent, prefix)
	if !strings.HasPrefix(h.ShutdownEvent, prefix) || len(suffix) != 32 {
		return errors.New("当前运行的是旧版服务，尚不支持任务栏关闭；请升级并重启该服务")
	}
	if _, err = hex.DecodeString(suffix); err != nil {
		return errors.New("服务关闭事件无效")
	}
	event, _, eventErr := kernel32.NewProc("OpenEventW").Call(2, 0, uintptr(unsafe.Pointer(wide(h.ShutdownEvent))))
	if event == 0 {
		return fmt.Errorf("无法连接服务关闭事件: %v", eventErr)
	}
	defer syscall.CloseHandle(syscall.Handle(event))
	process, _, processErr := kernel32.NewProc("OpenProcess").Call(0x100000, 0, uintptr(h.PID))
	if process == 0 {
		return fmt.Errorf("无法等待服务退出: %v", processErr)
	}
	defer syscall.CloseHandle(syscall.Handle(process))
	sent, _, signalErr := kernel32.NewProc("SetEvent").Call(event)
	if sent == 0 {
		return fmt.Errorf("发送关闭请求失败: %v", signalErr)
	}
	log.Printf("Requested graceful service shutdown pid=%d", h.PID)
	deadline := time.Now().Add(20 * time.Second)
	for time.Now().Before(deadline) {
		ended, _, _ := waitObject.Call(process, 100)
		if ended == 0 && !occupied(c) {
			r.Action = "stopped"
			r.ServerPID = 0
			return nil
		}
		time.Sleep(100 * time.Millisecond)
	}
	return errors.New("服务仍在完成当前请求，请稍后再次关闭；未强制结束进程")
}
