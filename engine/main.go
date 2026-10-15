// ebengine : moteur d'analyse et de transfert de Easy Backup.
//
// Communication : un événement JSON par ligne sur stdout.
// Annulation : écrire « cancel » sur stdin.
//
//	ebengine scan --root <dossier> [--hidden]
//	ebengine transfer --job <fichier.json>
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
	"sync"
)

const version = "1.0.0"

// english : langue des messages (--lang en), français par défaut.
var english bool

// T choisit le message dans la langue de l'interface.
func T(fr, en string) string {
	if english {
		return en
	}
	return fr
}

type emitter struct {
	mu     sync.Mutex
	w      *bufio.Writer
	enc    *json.Encoder
	failed bool
	onFail func()
}

func newEmitter(onFail func()) *emitter {
	w := bufio.NewWriterSize(os.Stdout, 256<<10)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	return &emitter{w: w, enc: enc, onFail: onFail}
}

// emit écrit un événement. Si l'interface a disparu (pipe cassé),
// on annule proprement le travail en cours au lieu de continuer à l'aveugle.
func (e *emitter) emit(v any) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.failed {
		return
	}
	err := e.enc.Encode(v)
	if err == nil {
		err = e.w.Flush()
	}
	if err != nil {
		e.failed = true
		e.onFail()
	}
}

type errorEvent struct {
	Type string `json:"type"`
	Msg  string `json:"msg"`
}

func watchStdin(cancel context.CancelFunc) {
	sc := bufio.NewScanner(os.Stdin)
	for sc.Scan() {
		if strings.TrimSpace(sc.Text()) == "cancel" {
			cancel()
			return
		}
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage :\n  ebengine scan --root <dossier> [--hidden]\n  ebengine transfer --job <fichier.json>\n  ebengine version")
	os.Exit(2)
}

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	out := newEmitter(cancel)
	go watchStdin(cancel)

	var err error
	switch os.Args[1] {
	case "scan":
		fs := flag.NewFlagSet("scan", flag.ExitOnError)
		root := fs.String("root", "", "dossier à analyser")
		hidden := fs.Bool("hidden", false, "inclure les fichiers cachés")
		lang := fs.String("lang", "fr", "langue des messages (fr, en)")
		fs.Parse(os.Args[2:])
		english = *lang == "en"
		err = runScan(ctx, out, *root, *hidden)
	case "transfer":
		fs := flag.NewFlagSet("transfer", flag.ExitOnError)
		jobPath := fs.String("job", "", "fichier JSON décrivant le transfert")
		lang := fs.String("lang", "fr", "langue des messages (fr, en)")
		fs.Parse(os.Args[2:])
		english = *lang == "en"
		err = runTransfer(ctx, out, *jobPath)
	case "version":
		fmt.Println(version)
		return
	default:
		usage()
	}
	if err != nil {
		out.emit(errorEvent{"error", err.Error()})
		os.Exit(1)
	}
}
