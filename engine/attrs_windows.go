//go:build windows

package main

import (
	"os"
	"syscall"
)

func fileAttrs(fi os.FileInfo) uint32 {
	if d, ok := fi.Sys().(*syscall.Win32FileAttributeData); ok {
		return d.FileAttributes
	}
	return 0
}
