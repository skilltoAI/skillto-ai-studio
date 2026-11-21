//go:build windows

package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

// Run the actual desktop binding without starting or registering a web service.
func TestOfflineWorkPreferences(t *testing.T) {
	python := os.Getenv("STASS_TEST_PYTHON")
	if python == "" {
		var err error
		python, err = exec.LookPath("python.exe")
		if err != nil {
			t.Skip("Set STASS_TEST_PYTHON to a Python 3.10+ executable")
		}
	}
	program, err := filepath.Abs("../../../..")
	if err != nil {
		t.Fatal(err)
	}
	a := Launcher{}
	a.cfg.PythonExecutable = python
	a.cfg.Program.Directory = program
	t.Setenv("STASS_PREFERENCES_DIR", t.TempDir())
	if _, err := a.WorkPreferences(`{"action":"save","groups":["teach"],"items":[],"revision":0}`); err != nil {
		t.Fatal(err)
	}
	text, err := a.WorkPreferences(`{"action":"navigation"}`)
	if err != nil {
		t.Fatal(err)
	}
	var value struct{ Groups []string }
	if err := json.Unmarshal([]byte(text), &value); err != nil || len(value.Groups) != 1 || value.Groups[0] != "teach" {
		t.Fatalf("unexpected preferences: %s", text)
	}
	if _, err := a.WorkPreferences(`{"action":"install"}`); err == nil {
		t.Fatal("bridge accepted unsupported action")
	}
}
