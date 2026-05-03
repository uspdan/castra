FROM php:8.2-apache
RUN apt-get update && apt-get install -y libsqlite3-dev && docker-php-ext-install pdo pdo_sqlite && rm -rf /var/lib/apt/lists/*
COPY index.php /var/www/html/index.php
COPY setup.php /var/www/html/setup.php
COPY style.css /var/www/html/style.css
RUN mkdir -p /var/www/data && chown www-data:www-data /var/www/data
RUN php /var/www/html/setup.php
EXPOSE 80
CMD ["apache2-foreground"]
