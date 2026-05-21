FROM php:8.2-apache

# Register .phtml and .phar as PHP-handled — many real shops do
# this without realising the upload filters they wrote only block
# the literal ".php" extension.
RUN { \
      echo 'AddType application/x-httpd-php .phtml .phar'; \
    } > /etc/apache2/conf-available/extra-php-handlers.conf \
 && a2enconf extra-php-handlers

COPY index.php /var/www/html/index.php
COPY style.css /var/www/html/style.css
COPY flag.txt /flag.txt
RUN chmod 0444 /flag.txt \
 && mkdir -p /var/www/html/uploads \
 && chown www-data:www-data /var/www/html/uploads \
 && chmod 0755 /var/www/html/uploads


# Sealed answer + flag sidecars staged by scripts/stage-answers.sh
# before docker build. Root-owned, mode 0600 inside the image —
# readable by the validator (root) and unreadable by the player
# (hunter).
COPY .answers.json /opt/answers.json
COPY .flag.txt /opt/flag.txt

RUN chmod 600 /opt/answers.json /opt/flag.txt && \
    chown root:root /opt/answers.json /opt/flag.txt

EXPOSE 80
CMD ["apache2-foreground"]
