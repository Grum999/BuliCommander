# Buli Commander :: Release 0.4.0a [2020-11-01]


## Implement *Auto close*
When all Krita windows are closed (ie: application is about to be closed) then close BuliCommander too.

## Implement *Auto open*

> Note: due to technical constraints, this function is available only for Krita 5.0.0

This option allows to open Buli Commander automatically at Krita's startup


## Implement *Override Krita open file dialog*

> Note: due to technical constraints, this function is available only for Krita 5.0.0

This option allows to replace Krita's open file dialog with Buli Commander:
- Open file shortcut execute Buli Commander
- Menu *File > Open...* execute Buli Commander


## Implement tool *Export file list*

The export file list allows to export current directory content or current selected files:
* As a text file
* As a Markdown file
* As a CSV file
* As a PDF document
* As a Krita image
* As a PNG/JPEG files

*Perimeter & properties definition*

![Export file list](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-4-0a_exportlist_001.png)


*Export as Markdown settings example*

![Export file list](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-4-0a_exportlist_002a.png)

*Export as PDF settings example*

![Export file list](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-4-0a_exportlist_002b.png)

*Export as Text results example*
```
Buli Commander v0.4.0a - File list exporter
--------------------------------------------------------------------------------

Exported from: /home/grum/Travail/Graphisme/Dessins/dessins/finished_sources/Chinese Girl
Exported at:   2020-11-01 00:12:54

┌─────────────────────────────────────────────────┬───────────────────┬───────────────────────┬───────────────────────────┐
│File name                                        │Date/Time          │Size (best binary unit)│Image size (width x height)│
├─────────────────────────────────────────────────┼───────────────────┼───────────────────────┼───────────────────────────┤
│chinese-girl--dress-middle-flowers.kra           │2020-03-14 23:49:12│                8.30MiB│                  1446x2433│
│chinese-girl--dress-phoenix.kra                  │2020-03-21 15:22:16│               34.64MiB│                  1650x1597│
│chinese-girl--work--layers-merged--black_test.kra│2020-03-29 14:23:09│               60.20MiB│                  3601x6953│
│chinese-girl--work--layers-merged.kra            │2020-03-29 10:08:38│               60.80MiB│                  3601x6953│
│chinese-girl-black-300x400-cmjn.kra              │2020-05-30 14:54:21│               38.17MiB│                  5207x7016│
│chinese-girl-black.kra                           │2020-03-29 14:56:02│               60.20MiB│                  3601x6953│
│chinese-girl-head.kra                            │2020-03-28 10:35:22│               10.02MiB│                  2792x2425│
│phoenix.kra                                      │2019-11-02 13:31:17│               48.91MiB│                  1650x1597│
└─────────────────────────────────────────────────┴───────────────────┴───────────────────────┴───────────────────────────┘

Directories:   0
Files:         8 (321.25MiB)
```


## Improve notification system

Add an optional great Buli Commander icon in taskbar :-)

![Systray Icon settings](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-4-0a_settings_systray.png)

