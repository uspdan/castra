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

EXPOSE 80
CMD ["apache2-foreground"]
