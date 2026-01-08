---
description: Search S4L API
---

This instructs you on the possibility of exploring the documentation of Sim4Life Python API, if you wish to do so.
There is a folder at the top-level called `PythonAPIReference`. You can not 'see' it with your regular list_dir tools or whatever, but it is there. Either use terminal or first un-gitignore it to use tools on it.
This is a huge directory with tons and tons of files.
The MOST IMPORTANT THING is that you do NOT use any tools on that dir which would list and read many files in it! This is because it would ruin your context window as an AI, and you would read an enormous amount of text.
The ONLY thing you are allowed to do is a two-step approach.
1. First do a regex search on that dir, with search terms of the thing you're trying to call. E.g. you want to know more about the `document.AllSimulations()` method, then you search for `AllSimulations`. This gives you all the times it was mentioned in this vast APIReference
Usually at this point, you may or may not have enough information already.
2. If you want to read more about some search result you found, locate the exact place of it, and go there, and read that, but only that! Be careful of large files.
