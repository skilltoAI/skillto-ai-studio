//go:build windows

package main

func stop(c config, r *receipt) error { return manage(c, "stop", r) }
