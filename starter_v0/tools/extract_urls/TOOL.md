---
name: extract_urls
track: core
kind: local_parser
requires_env: []
inputs: [text]
outputs: [urls, count]
side_effect: false
---
# extract_urls

Extracts all HTTP/HTTPS URLs from user-provided text. It does not fetch the URLs.
