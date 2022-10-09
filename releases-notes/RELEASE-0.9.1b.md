# Buli Commander :: Release 0.9.1b [2022-10-09]

## Improve performances

### Reduce initialization time & folder analysis
[Feature request #23](https://github.com/Grum999/BuliCommander/issues/23)

Time execution to open plugin main window was long (~2.28s) and also, time needed to scan & analyze folder content was not optimized


Test on 14250 files, 110GB
# Load files metadata
| #Threads | Without cache initialized | With cache initialized |
| --- | --- | --- |
| 1 *(v0.9.1b)* | 10.44s | 3.56s |
| 24 *(v0.9.0b)* | 19.67s | 6.52s |

# Load files thumbnails
| #Threads | Without cache initialized | With cache initialized |
| --- | --- | --- |
| 1 *(test)* | 1542s | 2.61s |
| 14 *(v0.9.1b)* (60% of available threads) | 428s | 2.70s |
| 24 *(v0.9.0b)* | 436s | 2.75s |

Plugin initialization: reduced from ~2.28s to 0.85s

