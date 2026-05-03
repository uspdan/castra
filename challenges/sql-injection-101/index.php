<?php
$error = '';
$profile = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';
    $db = new PDO('sqlite:/var/www/data/users.db');
    // VULNERABLE: Direct string interpolation
    $query = "SELECT * FROM users WHERE username = '$username' AND password = '$password'";
    $result = $db->query($query);
    if ($result) {
        $user = $result->fetch(PDO::FETCH_ASSOC);
        if ($user) {
            $profile = $user['profile'];
        } else {
            $error = 'Invalid credentials';
        }
    } else {
        $error = 'Query error';
    }
}
?>
<!DOCTYPE html>
<html>
<head><title>SecureCorp Login</title><link rel="stylesheet" href="style.css"></head>
<body>
<div class="container">
    <h1>SecureCorp Portal</h1>
    <?php if ($profile): ?>
        <div class="success">
            <h2>Welcome, Admin</h2>
            <p class="profile"><?= htmlspecialchars($profile) ?></p>
        </div>
    <?php else: ?>
        <?php if ($error): ?><div class="error"><?= htmlspecialchars($error) ?></div><?php endif; ?>
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
    <?php endif; ?>
</div>
</body>
</html>
