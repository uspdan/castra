FROM php:8.2-apache
RUN apt-get update && apt-get install -y libsqlite3-dev && docker-php-ext-install pdo pdo_sqlite && rm -rf /var/lib/apt/lists/*
COPY index.php /var/www/html/index.php
COPY setup.php /var/www/html/setup.php
COPY style.css /var/www/html/style.css
RUN mkdir -p /var/www/data && chown www-data:www-data /var/www/data
RUN php /var/www/html/setup.php

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
