<?php
// VaultPin — internal "PIN unlock" page.
//
// The admin's chosen PIN is hashed with MD5 and stored. The check
// compares the submitted PIN's hash against the stored hash using
// PHP's loose-equality operator `==`. That comparison treats any
// string that *looks like* a number in scientific notation as a
// float — including strings of the form "0e..." which are all
// treated as 0.0.
//
// If the stored hash happens to fit that shape, the check passes
// for any input whose md5() also fits the shape. Welcome to
// "magic hashes".
//
// Admin's real PIN was 240610708 (md5 -> 0e462097431906509019562988736854).
// Don't tell anyone.

$ADMIN_HASH = '0e462097431906509019562988736854';
$FLAG = 'CTF{REDACTED}';

$error = '';
$flag = '';
$debug_hash = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $pin = $_POST['pin'] ?? '';
    if (is_string($pin) && $pin !== '') {
        $debug_hash = md5($pin);
        // VULNERABLE: loose `==` between two `0e...` strings collapses
        // both to float 0.0 and returns true.
        if ($debug_hash == $ADMIN_HASH) {
            $flag = $FLAG;
        } else {
            $error = 'Wrong PIN.';
        }
    } else {
        $error = 'PIN must be a non-empty string.';
    }
}
?>
<!DOCTYPE html>
<html>
<head><title>VaultPin</title><link rel="stylesheet" href="style.css"></head>
<body>
<div class="container">
    <h1>VaultPin</h1>
    <p class="subtitle">internal PIN unlock — admin only</p>

    <?php if ($flag): ?>
        <div class="success">
            <h2>Access granted.</h2>
            <p class="profile"><?= htmlspecialchars($flag) ?></p>
        </div>
    <?php else: ?>
        <?php if ($error): ?><div class="error"><?= htmlspecialchars($error) ?></div><?php endif; ?>
        <form method="POST">
            <input type="text" name="pin" placeholder="PIN" autocomplete="off" required>
            <button type="submit">Unlock</button>
        </form>
        <?php if ($debug_hash): ?>
            <p class="debug">md5(your input) = <code><?= htmlspecialchars($debug_hash) ?></code></p>
        <?php endif; ?>
        <details class="hint">
          <summary>Hint</summary>
          <p>The check is roughly:
            <code>if (md5($_POST['pin']) == $stored_hash)</code>.
            PHP's <code>==</code> has opinions about strings that
            happen to look like numbers.</p>
        </details>
    <?php endif; ?>
</div>
</body>
</html>
