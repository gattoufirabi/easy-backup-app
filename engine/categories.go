package main

import (
	"path/filepath"
	"strings"
)

// Les noms doivent correspondre à ORDER dans easybackup/categories.py.
var categories = map[string][]string{
	"Images": {
		".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp",
		".heic", ".heif", ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng",
		".orf", ".rw2", ".svg", ".ico", ".psd",
	},
	"Vidéos": {
		".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
		".mpg", ".mpeg", ".3gp", ".mts", ".m2ts", ".ts", ".vob",
	},
	"Audio": {
		".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus",
		".aiff", ".mid", ".midi",
	},
	"Documents": {
		".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".xls",
		".xlsx", ".ods", ".csv", ".ppt", ".pptx", ".odp", ".epub",
		".pages", ".numbers", ".key",
	},
	"Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
}

const otherCategory = "Autres"

var byExt = func() map[string]string {
	m := map[string]string{}
	for cat, exts := range categories {
		for _, ext := range exts {
			m[ext] = cat
		}
	}
	return m
}()

func categoryFor(name string) string {
	if cat, ok := byExt[strings.ToLower(filepath.Ext(name))]; ok {
		return cat
	}
	return otherCategory
}
