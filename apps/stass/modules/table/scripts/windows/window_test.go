//go:build windows

package main

import (
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestVerifyBeamDistinguishesLegacyRelease(t *testing.T) {
	root := t.TempDir()
	manifest := []byte(`{"files":{"program/service.py":"irrelevant"}}`)
	if err := os.WriteFile(filepath.Join(root, "release.json"), manifest, 0600); err != nil {
		t.Fatal(err)
	}
	if err := verifyBeam(root, fmt.Sprintf("%x", sha256.Sum256(manifest))); !errors.Is(err, errBeamNotIncluded) {
		t.Fatalf("legacy release should report that Beam is absent: %v", err)
	}
}

func TestVerifyBeamRejectsTamperedOrUnlistedRuntime(t *testing.T) {
	root := t.TempDir()
	dir := filepath.Join(root, "beam")
	if err := os.Mkdir(dir, 0700); err != nil {
		t.Fatal(err)
	}
	exe := filepath.Join(dir, "SkilltoBeam.exe")
	original := []byte("original payload")
	if err := os.WriteFile(exe, original, 0600); err != nil {
		t.Fatal(err)
	}
	manifest, err := json.Marshal(map[string]any{"files": map[string]string{
		"beam/SkilltoBeam.exe": fmt.Sprintf("%x", sha256.Sum256(original)),
	}})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "release.json"), manifest, 0600); err != nil {
		t.Fatal(err)
	}
	digest := fmt.Sprintf("%x", sha256.Sum256(manifest))
	if err := verifyBeam(root, digest); err != nil {
		t.Fatal(err)
	}
	if err := verifyBeam(root, "wrong"); err == nil {
		t.Fatal("wrong manifest digest was accepted")
	}
	extra := filepath.Join(dir, "unlisted.dll")
	if err := os.WriteFile(extra, []byte("extra"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := verifyBeam(root, digest); err == nil {
		t.Fatal("unlisted DLL was accepted")
	}
	if err := os.Remove(extra); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(exe, []byte("changed payload"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := verifyBeam(root, digest); err == nil {
		t.Fatal("tampered EXE was accepted")
	}
}
