//go:build windows

package main

import (
	"errors"
	"syscall"
)

// messages {français, anglais}
var friendlyErrors = map[syscall.Errno][2]string{
	2:   {"fichier introuvable (déplacé ou supprimé ?)", "file not found (moved or deleted?)"},
	3:   {"chemin introuvable", "path not found"},
	5:   {"accès refusé", "access denied"},
	19:  {"le support est protégé en écriture", "the drive is write-protected"},
	21:  {"le support n'est pas prêt (débranché ?)", "the drive is not ready (unplugged?)"},
	32:  {"fichier utilisé par un autre programme", "file is in use by another program"},
	33:  {"fichier verrouillé par un autre programme", "file is locked by another program"},
	39:  {"le support de destination est plein", "the destination drive is full"},
	112: {"le support de destination est plein", "the destination drive is full"},
	1117: {"erreur d'entrée/sortie (support défectueux ou débranché ?)",
		"I/O error (faulty or unplugged drive?)"},
	1167: {"le support n'est plus connecté", "the drive is no longer connected"},
	483:  {"le support n'est plus connecté", "the drive is no longer connected"},
}

// Erreurs qui concernent tout le support : inutile de continuer.
var fatalErrors = map[syscall.Errno]bool{19: true, 21: true, 39: true, 112: true, 1167: true, 483: true}

func friendlyError(err error) string {
	var errno syscall.Errno
	if errors.As(err, &errno) {
		if msg, ok := friendlyErrors[errno]; ok {
			return T(msg[0], msg[1])
		}
	}
	return err.Error()
}

func isFatal(err error) bool {
	var errno syscall.Errno
	return errors.As(err, &errno) && fatalErrors[errno]
}
