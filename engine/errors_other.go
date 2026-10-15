//go:build !windows

package main

import (
	"errors"
	"syscall"
)

func friendlyError(err error) string { return err.Error() }

func isFatal(err error) bool {
	return errors.Is(err, syscall.ENOSPC) || errors.Is(err, syscall.EROFS)
}
