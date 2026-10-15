package main

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Transfert de dossiers entiers : toute l'arborescence est reproduite
// (sous-dossiers vides et fichiers cachés compris).

type jobDir struct {
	Path string `json:"path"`
	Rel  string `json:"rel"`
	Size int64  `json:"size"`
}

type dirStartEvent struct {
	Type  string `json:"type"`
	Index int    `json:"index"`
	Total int    `json:"total"`
	Name  string `json:"name"`
}

type dirResultEvent struct {
	Type   string `json:"type"`
	Index  int    `json:"index"`
	Status string `json:"status"`           // ok | skipped | failed
	Reason string `json:"reason,omitempty"` // exists | same_path
	Target string `json:"target,omitempty"`
	Files  int    `json:"files"`  // fichiers transférés
	Failed int    `json:"failed"` // fichiers en erreur
	Error  string `json:"error,omitempty"`
}

type dirFileErrorEvent struct {
	Type  string `json:"type"`
	Index int    `json:"index"`
	Path  string `json:"path"`
	Error string `json:"error"`
}

type dirOutcome struct {
	status, reason, target string
	files, failed          int
	err                    error
}

// isLink : lien symbolique ou jonction (on ne les suit jamais).
func isLink(d fs.DirEntry) bool {
	if d.Type()&fs.ModeSymlink != 0 {
		return true
	}
	if info, err := d.Info(); err == nil {
		return fileAttrs(info)&attrReparsePoint != 0 && d.IsDir()
	}
	return false
}

func dirSize(root string) int64 {
	var total int64
	filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if path != root && isLink(d) {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if d.Type().IsRegular() {
			if info, err := d.Info(); err == nil {
				total += info.Size()
			}
		}
		return nil
	})
	return total
}

func uniqueDirPath(path string) string {
	for i := 1; ; i++ {
		candidate := fmt.Sprintf("%s (%d)", path, i)
		if _, err := os.Lstat(candidate); os.IsNotExist(err) {
			return candidate
		}
	}
}

func isInside(child, parent string) bool {
	c := strings.ToLower(filepath.Clean(child)) + string(filepath.Separator)
	p := strings.ToLower(filepath.Clean(parent)) + string(filepath.Separator)
	return strings.HasPrefix(c, p)
}

func (t *transfer) dirTarget(d jobDir, src string) string {
	if t.job.Layout == "keep_tree" && d.Rel != "" {
		return filepath.Join(t.job.Dest, t.label, d.Rel)
	}
	return filepath.Join(t.job.Dest, filepath.Base(src))
}

func (t *transfer) processDir(index int, d jobDir, done *int64) dirOutcome {
	src, err := filepath.Abs(d.Path)
	if err != nil {
		return dirOutcome{err: err}
	}
	target := t.dirTarget(d, src)
	if strings.EqualFold(filepath.Clean(src), filepath.Clean(target)) {
		return dirOutcome{status: "skipped", reason: "same_path", target: target}
	}
	if isInside(target, src) {
		return dirOutcome{target: target,
			err: errors.New(T("la destination se trouve à l'intérieur de ce dossier",
				"the destination is inside this folder"))}
	}
	si, err := os.Stat(src)
	if err != nil {
		return dirOutcome{target: target, err: err}
	}
	if !si.IsDir() {
		return dirOutcome{target: target, err: fmt.Errorf(T("%s n'est pas un dossier", "%s is not a folder"), src)}
	}

	exists := false
	if _, err := os.Lstat(target); err == nil {
		switch t.job.Conflict {
		case "skip":
			return dirOutcome{status: "skipped", reason: "exists", target: target}
		case "rename":
			target = uniqueDirPath(target)
		default: // overwrite : fusion dans le dossier existant
			exists = true
		}
	}
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return dirOutcome{target: target, err: err}
	}

	move := t.job.Mode == "move"
	if move && !exists && sameVolume(src, target) {
		// même disque : un seul renommage, instantané quelle que soit la taille
		if err := os.Rename(src, target); err == nil {
			return dirOutcome{status: "ok", target: target, files: -1}
		}
		// sinon (fichier ouvert…), on déplace fichier par fichier
	}

	files, failed, err := t.copyTree(index, src, target, done)
	if err != nil {
		return dirOutcome{target: target, files: files, failed: failed, err: err}
	}
	if move {
		removeEmptyDirs(src)
	}
	if failed > 0 {
		return dirOutcome{target: target, files: files, failed: failed,
			err: fmt.Errorf(T("%d fichier(s) n'ont pas pu être transférés",
				"%d file(s) could not be transferred"), failed)}
	}
	return dirOutcome{status: "ok", target: target, files: files}
}

// copyTree reproduit src dans dst. Les erreurs sur un fichier sont signalées
// sans arrêter le dossier ; seules l'annulation et les erreurs fatales l'arrêtent.
func (t *transfer) copyTree(index int, src, dst string, done *int64) (files, failed int, err error) {
	walkErr := filepath.WalkDir(src, func(path string, d fs.DirEntry, werr error) error {
		if t.ctx.Err() != nil {
			return t.ctx.Err()
		}
		rel, _ := filepath.Rel(src, path)
		target := filepath.Join(dst, rel)
		report := func(e error) error {
			failed++
			t.out.emit(dirFileErrorEvent{"dir_file_error", index, path, friendlyError(e)})
			if isFatal(e) {
				return e
			}
			return nil
		}
		if werr != nil {
			if r := report(werr); r != nil {
				return r
			}
			if d != nil && d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if path != src && isLink(d) {
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		if d.IsDir() {
			if err := os.MkdirAll(target, 0o755); err != nil {
				if r := report(err); r != nil {
					return r
				}
				return filepath.SkipDir
			}
			return nil
		}
		if !d.Type().IsRegular() {
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return report(err)
		}
		if err := t.transferFile(path, target, info, *done); err != nil {
			if errors.Is(err, context.Canceled) {
				return err
			}
			return report(err)
		}
		files++
		*done += info.Size()
		if now := time.Now(); now.Sub(t.lastEmit) >= 100*time.Millisecond {
			t.lastEmit = now
			t.out.emit(transferProgressEvent{"progress", *done, t.total})
		}
		return nil
	})
	return files, failed, walkErr
}

// removeEmptyDirs supprime les dossiers vidés par un déplacement (du plus
// profond au plus haut) ; les dossiers encore non vides sont conservés.
func removeEmptyDirs(root string) {
	var dirs []string
	filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err == nil && d.IsDir() {
			if path != root && isLink(d) {
				return filepath.SkipDir
			}
			dirs = append(dirs, path)
		}
		return nil
	})
	for i := len(dirs) - 1; i >= 0; i-- {
		os.Remove(dirs[i]) // échoue sans danger si le dossier n'est pas vide
	}
}
