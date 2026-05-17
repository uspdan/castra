<?php
// PicProfile — profile photo upload.
//
// We "carefully" reject any file whose extension is one of our
// known-PHP extensions before storing it under /uploads/, which
// is served directly by Apache. The blacklist is the lesson.

$err = '';
$ok = '';
$uploaded_url = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_FILES['photo'])) {
    $orig = $_FILES['photo']['name'];
    $name = basename(preg_replace('/[^A-Za-z0-9._-]/', '_', $orig));

    // VULNERABLE: blacklist of "PHP-ish" extensions. Misses
    // anything Apache has been taught to also treat as PHP — in
    // this image, .phtml and .phar (see Dockerfile).
    $forbidden = ['php', 'php5', 'php7', 'pht'];

    $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
    if (in_array($ext, $forbidden, true)) {
        $err = "Disallowed extension: .$ext (only image extensions please)";
    } elseif ($_FILES['photo']['size'] > 1024 * 1024) {
        $err = 'File too large (1 MB limit).';
    } else {
        $dest_dir = __DIR__ . '/uploads';
        $dest = $dest_dir . '/' . $name;
        if (move_uploaded_file($_FILES['photo']['tmp_name'], $dest)) {
            chmod($dest, 0644);
            $ok = "Uploaded.";
            $uploaded_url = "/uploads/" . $name;
        } else {
            $err = 'Upload failed.';
        }
    }
}
?>
<!DOCTYPE html>
<html>
<head><title>PicProfile</title><link rel="stylesheet" href="style.css"></head>
<body>
<div class="container">
    <h1>PicProfile</h1>
    <p class="subtitle">upload your profile photo — image files only</p>

    <?php if ($err): ?><div class="error"><?= htmlspecialchars($err) ?></div><?php endif; ?>
    <?php if ($ok): ?>
        <div class="success">
            <strong><?= htmlspecialchars($ok) ?></strong>
            <p>Available at <a href="<?= htmlspecialchars($uploaded_url) ?>"><code><?= htmlspecialchars($uploaded_url) ?></code></a></p>
        </div>
    <?php endif; ?>

    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="photo" required>
        <button type="submit">Upload</button>
    </form>

    <details class="hint">
      <summary>What's filtered?</summary>
      <p>We reject anything ending in <code>.php</code>, <code>.php5</code>, <code>.php7</code>, or <code>.pht</code>.
         Everything else gets stored under <code>/uploads/</code>.</p>
    </details>
</div>
</body>
</html>
