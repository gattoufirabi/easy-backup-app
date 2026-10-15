package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// Dossiers système ignorés à la racine d'un disque.
var rootSkip = map[string]bool{
	"$recycle.bin": true, "system volume information": true, "windows": true,
	"program files": true, "program files (x86)": true, "programdata": true,
	"recovery": true, "$windows.~bt": true, "$windows.~ws": true,
	"$winreagent": true, "msocache": true,
}

// Dossiers ignorés partout.
var anySkip = map[string]bool{
	"appdata": true, "node_modules": true, ".git": true, "$recycle.bin": true,
	"__pycache__": true,
}

const (
	scanParallelism = 16 // lectures de dossiers simultanées
	batchSize       = 1000
)

type fileInfo struct {
	Path  string  `json:"p"`
	Rel   string  `json:"r"`
	Size  int64   `json:"s"`
	Mtime float64 `json:"m"`
	Cat   string  `json:"c"`
}

type filesEvent struct {
	Type  string     `json:"type"`
	Files []fileInfo `json:"files"`
}

type scanProgressEvent struct {
	Type  string `json:"type"`
	Count int    `json:"count"`
	Bytes int64  `json:"bytes"`
	Dirs  int64  `json:"dirs"`
	Dir   string `json:"dir"`
}

type scanDoneEvent struct {
	Type      string `json:"type"`
	Count     int    `json:"count"`
	Errors    int64  `json:"errors"`
	Cancelled bool   `json:"cancelled"`
}

type scanner struct {
	ctx     context.Context
	root    string
	hidden  bool
	sem     chan struct{}
	wg      sync.WaitGroup
	files   chan fileInfo
	current atomic.Value // dernier dossier lu
	errs    atomic.Int64 // dossiers illisibles
	dirs    atomic.Int64 // dossiers lus
}

func runScan(ctx context.Context, out *emitter, root string, hidden bool) error {
	if root == "" {
		return errors.New(T("--root est obligatoire", "--root is required"))
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		return err
	}
	st, err := os.Stat(abs)
	if err != nil {
		return fmt.Errorf("%s : %s", abs, friendlyError(err))
	}
	if !st.IsDir() {
		return fmt.Errorf(T("%s n'est pas un dossier", "%s is not a folder"), abs)
	}

	s := &scanner{
		ctx:    ctx,
		root:   abs,
		hidden: hidden,
		sem:    make(chan struct{}, scanParallelism),
		files:  make(chan fileInfo, 4096),
	}
	s.current.Store(abs)
	s.wg.Add(1)
	go s.walk(abs)
	go func() {
		s.wg.Wait()
		close(s.files)
	}()

	batch := make([]fileInfo, 0, batchSize)
	count := 0
	var bytes int64
	flush := func() {
		if len(batch) > 0 {
			out.emit(filesEvent{"files", batch})
			batch = make([]fileInfo, 0, batchSize)
		}
	}
	tick := time.NewTicker(150 * time.Millisecond)
	defer tick.Stop()

loop:
	for {
		select {
		case f, ok := <-s.files:
			if !ok {
				break loop
			}
			batch = append(batch, f)
			count++
			bytes += f.Size
			if len(batch) >= batchSize {
				flush()
			}
		case <-tick.C:
			flush()
			out.emit(scanProgressEvent{"progress", count, bytes, s.dirs.Load(), s.current.Load().(string)})
		}
	}
	flush()
	out.emit(scanDoneEvent{"done", count, s.errs.Load(), ctx.Err() != nil})
	return nil
}

func (s *scanner) walk(dir string) {
	defer s.wg.Done()
	if s.ctx.Err() != nil {
		return
	}
	s.sem <- struct{}{}
	entries, err := os.ReadDir(dir)
	<-s.sem
	if err != nil && len(entries) == 0 {
		s.errs.Add(1)
		return
	}
	s.current.Store(dir)
	s.dirs.Add(1)
	atRoot := filepath.Dir(dir) == dir

	for _, e := range entries {
		if s.ctx.Err() != nil {
			return
		}
		name := e.Name()
		info, err := e.Info()
		if err != nil {
			continue
		}
		attrs := fileAttrs(info)
		if !s.hidden && (strings.HasPrefix(name, ".") || attrs&(attrHidden|attrSystem) != 0) {
			continue
		}
		full := filepath.Join(dir, name)

		if e.IsDir() {
			low := strings.ToLower(name)
			// les jonctions / liens de dossiers peuvent créer des boucles
			if attrs&attrReparsePoint != 0 || anySkip[low] || (atRoot && rootSkip[low]) {
				continue
			}
			s.wg.Add(1)
			go s.walk(full)
			continue
		}
		if !info.Mode().IsRegular() { // liens symboliques, périphériques…
			continue
		}
		rel, err := filepath.Rel(s.root, full)
		if err != nil {
			rel = name
		}
		f := fileInfo{
			Path:  full,
			Rel:   rel,
			Size:  info.Size(),
			Mtime: float64(info.ModTime().UnixNano()) / 1e9,
			Cat:   categoryFor(name),
		}
		select {
		case s.files <- f:
		case <-s.ctx.Done():
			return
		}
	}
}
