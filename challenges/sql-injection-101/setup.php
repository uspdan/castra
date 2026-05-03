<?php
$db = new PDO('sqlite:/var/www/data/users.db');
$db->exec("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, profile TEXT)");
$db->exec("INSERT OR IGNORE INTO users (id, username, password, profile) VALUES (1, 'admin', 's3cur3p@ssw0rd!', 'CTF{REDACTED}')");
$db->exec("INSERT OR IGNORE INTO users (id, username, password, profile) VALUES (2, 'guest', 'guest123', 'Regular user account')");
echo "Database initialized.\n";
?>
