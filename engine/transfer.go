package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

const (
	copyBufSize = 4 << 20
	partSuffix  = ".ebpart" // fichier temporaire pendant la copie
)

type jobFile struct {
	Path     string `json:"path"`
	Rel      string `json:"rel"`
	Category string `json:"category"`
	Size     int64  `json:"size"`
}

type job struct {
	Dest       string    `json:"dest"`
	SourceRoot string    `json:"source_root"`
	Mode       string    `json:"mode"`     // copy | move
	Layout     string    `json:"layout"`   // by_type | keep_tree | flat
	Conflict   string    `json:"conflict"` // rename | skip | overwrite
	Files      []jobFile `json:"files"`
	Dirs       []jobDir  `json:"dirs"` // dossiers entiers, traités avant les fichiers
}

type fileStartEvent struct {
	Type  string `json:"type"`
	Index int    `json:"index"`
	Total int    `json:"total"`
	Name  string `json:"name"`
}

type transferProgressEvent struct {
	Type  string `json:"type"`
	Done  int64  `json:"done"`
	Total int64  `json:"total"`
}

type resultEvent struct {
	Type   string `json:"type"`
	Index  int    `json:"index"`
	Status string `json:"status"`           // ok | skipped | failed
	Reason string `json:"reason,omitempty"` // exists | same_path (si skipped)
	Target string `json:"target,omitempty"`
	Error  string `json:"error,omitempty"`
}

type transferDoneEvent struct {
	Type      string `json:"type"`
	Cancelled bool   `json:"cancelled"`
}

type transfer struct {
	ctx      context.Context
	out      *emitter
	job      job
	label    string
	buf      []byte
	total    int64
	lastEmit time.Time
}

func runTransfer(ctx context.Context, out *emitter, jobPath string) error {
	if jobPath == "" {
		return errors.New(T("--job est obligatoire", "--job is required"))
	}
	data, err := os.ReadFile(jobPath)
	if err != nil {
		return err
	}
	var j job
	if err := json.Unmarshal(data, &j); err != nil {
		return fmt.Errorf(T("fichier de tâche invalide : %w", "invalid job file: %w"), err)
	}
	if j.Dest == "" {
		return errors.New(T("destination manquante", "missing destination"))
	}
	if j.Dest, err = filepath.Abs(j.Dest); err != nil {
		return err
	}

	t := &transfer{ctx: ctx, out: out, job: j, label: sourceLabel(j.SourceRoot),
		buf: make([]byte, copyBufSize)}
	for _, f := range j.Files {
		t.total += f.Size
	}
	dirSizes := make([]int64, len(j.Dirs))
	for i, d := range j.Dirs { // taille exacte (fichiers cachés compris)
		dirSizes[i] = dirSize(d.Path)
		t.total += dirSizes[i]
	}

	var done int64
	cancelled := false
	out.emit(transferProgressEvent{"progress", 0, t.total})

	for i, d := range j.Dirs {
		if ctx.Err() != nil {
			cancelled = true
			break
		}
		out.emit(dirStartEvent{"dir_start", i, len(j.Dirs), filepath.Base(d.Path)})
		start := done
		res := t.processDir(i, d, &done)
		if errors.Is(res.err, context.Canceled) {
			cancelled = true
			break
		}
		ev := dirResultEvent{Type: "dir_result", Index: i, Status: res.status,
			Reason: res.reason, Target: res.target, Files: res.files, Failed: res.failed}
		if res.err != nil {
			ev.Status = "failed"
			ev.Error = friendlyError(res.err)
		}
		out.emit(ev)
		if res.err != nil && isFatal(res.err) {
			return fmt.Errorf(T("transfert interrompu : %s", "transfer interrupted: %s"), ev.Error)
		}
		done = start + dirSizes[i] // recale la progression (fichiers ignorés…)
		out.emit(transferProgressEvent{"progress", done, t.total})
	}

	for i, f := range j.Files {
		if cancelled {
			break
		}
		if ctx.Err() != nil {
			cancelled = true
			break
		}
		out.emit(fileStartEvent{"file_start", i, len(j.Files), filepath.Base(f.Path)})
		res := t.process(f, done)
		if errors.Is(res.err, context.Canceled) {
			cancelled = true
			break
		}
		ev := resultEvent{Type: "result", Index: i, Status: res.status,
			Reason: res.reason, Target: res.target}
		if res.err != nil {
			ev.Status = "failed"
			ev.Error = friendlyError(res.err)
		}
		out.emit(ev)
		if res.err != nil && isFatal(res.err) {
			return fmt.Errorf(T("transfert interrompu : %s", "transfer interrupted: %s"), ev.Error)
		}
		done += f.Size
		out.emit(transferProgressEvent{"progress", done, t.total})
	}
	out.emit(transferDoneEvent{"done", cancelled})
	return nil
}

type outcome struct {
	status, reason, target string
	err                    error
}

func (t *transfer) targetFor(f jobFile) string {
	name := filepath.Base(f.Path)
	switch t.job.Layout {
	case "by_type":
		return filepath.Join(t.job.Dest, f.Category, name)
	case "keep_tree":
		return filepath.Join(t.job.Dest, t.label, f.Rel)
	default:
		return filepath.Join(t.job.Dest, name)
	}
}

func (t *transfer) process(f jobFile, done int64) outcome {
	target := t.targetFor(f)
	src, err := filepath.Abs(f.Path)
	if err != nil {
		return outcome{target: target, err: err}
	}
	if strings.EqualFold(filepath.Clean(src), filepath.Clean(target)) {
		return outcome{status: "skipped", reason: "same_path", target: target}
	}
	si, err := os.Stat(src)
	if err != nil {
		return outcome{target: target, err: err}
	}
	if !si.Mode().IsRegular() {
		return outcome{target: target, err: fmt.Errorf(T("%s n'est pas un fichier", "%s is not a file"), src)}
	}

	if _, err := os.Lstat(target); err == nil {
		switch t.job.Conflict {
		case "skip":
			return outcome{status: "skipped", reason: "exists", target: target}
		case "rename":
			target = uniquePath(target)
		}
	}
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return outcome{target: target, err: err}
	}

	if err := t.transferFile(src, target, si, done); err != nil {
		return outcome{target: target, err: err}
	}
	return outcome{status: "ok", target: target}
}

// transferFile copie ou déplace un fichier vers dst (dossier parent existant).
func (t *transfer) transferFile(src, dst string, si os.FileInfo, base int64) error {
	move := t.job.Mode == "move"
	if move && sameVolume(src, dst) {
		// simple renommage sur le même disque : instantané
		return os.Rename(src, dst)
	}
	if err := t.copyFile(src, dst, si, base, move); err != nil {
		return err
	}
	if move {
		if err := os.Remove(src); err != nil {
			return fmt.Errorf(T("copié, mais l'original n'a pas pu être supprimé : %s",
				"copied, but the original could not be deleted: %s"), friendlyError(err))
		}
	}
	return nil
}

// copyFile copie vers un fichier temporaire puis le renomme : la destination
// n'existe jamais à moitié écrite, même en cas d'annulation ou de débranchement.
func (t *transfer) copyFile(src, dst string, si os.FileInfo, base int64, syncToDisk bool) (err error) {
	tmp := dst + partSuffix
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	defer func() {
		if err != nil {
			out.Close()
			os.Remove(tmp)
		}
	}()

	var written int64
	for {
		if t.ctx.Err() != nil {
			return t.ctx.Err()
		}
		nr, rerr := in.Read(t.buf)
		if nr > 0 {
			nw, werr := out.Write(t.buf[:nr])
			written += int64(nw)
			if werr != nil {
				return werr
			}
			if nw != nr {
				return io.ErrShortWrite
			}
			if now := time.Now(); now.Sub(t.lastEmit) >= 100*time.Millisecond {
				t.lastEmit = now
				t.out.emit(transferProgressEvent{"progress", base + written, t.total})
			}
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return rerr
		}
	}
	if written != si.Size() {
		return fmt.Errorf(T("taille copiée (%d o) différente de l'original (%d o) : "+
			"fichier modifié pendant la copie ?",
			"copied size (%d B) differs from the original (%d B): "+
				"was the file modified during the copy?"), written, si.Size())
	}
	if syncToDisk { // avant de supprimer l'original, on s'assure que tout est écrit
		if err = out.Sync(); err != nil {
			return err
		}
	}
	if err = out.Close(); err != nil {
		return err
	}
	_ = os.Chtimes(tmp, si.ModTime(), si.ModTime()) // conserve la date de modification
	return os.Rename(tmp, dst)
}

func uniquePath(path string) string {
	ext := filepath.Ext(path)
	base := strings.TrimSuffix(path, ext)
	for i := 1; ; i++ {
		candidate := fmt.Sprintf("%s (%d)%s", base, i, ext)
		if _, err := os.Lstat(candidate); os.IsNotExist(err) {
			return candidate
		}
	}
}

var nonWord = regexp.MustCompile(`[^\p{L}\p{N}_-]+`)

// sourceLabel : nom du dossier racine pour l'option « conserver l'arborescence ».
func sourceLabel(root string) string {
	if root == "" {
		return "Source"
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		abs = root
	}
	vol := filepath.VolumeName(abs)
	rest := strings.Trim(abs[len(vol):], `\/`)
	if rest != "" {
		return filepath.Base(rest)
	}
	if label := strings.Trim(nonWord.ReplaceAllString(vol, "_"), "_"); label != "" {
		return T("Disque_", "Drive_") + label
	}
	return "Source"
}

func sameVolume(a, b string) bool {
	return strings.EqualFold(filepath.VolumeName(a), filepath.VolumeName(b))
}
