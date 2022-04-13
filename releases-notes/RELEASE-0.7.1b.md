# Buli Commander :: Release 0.7.1b [2022-04-13]

> This is a bug fix release for a regression introduced with release 0.7.0b
> Please check [release note for Buli Commander 0.7.0b](./RELEASE-0.7.0b.md) for detailled list of change implemented from v0.6.0a


## Fix bugs
One bug is fixed

### Thumbnail loading
Thumbnails were loaded even if view were not visible/not in thumbnail mode.

Also thumbnail load was executed in parallel on list&grid view and generate a performance problem.

Fix this to load thumbnail only if needed
