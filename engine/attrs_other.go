//go:build !windows

package main

import "os"

func fileAttrs(fi os.FileInfo) uint32 { return 0 }
