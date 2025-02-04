# Install Browser, OS dependencies, and Python modules
FROM public.ecr.aws/lambda/python:3.10 AS lambda-base

# Install OS dependencies
RUN yum install -y -q \
    xz atk cups-libs gtk3 libXcomposite alsa-lib tar \
    libXcursor libXdamage libXext libXi libXrandr libXScrnSaver \
    libXtst pango at-spi2-atk libXt xorg-x11-server-Xvfb \
    xorg-x11-xauth dbus-glib dbus-glib-devel unzip bzip2

# Copy required files
COPY requirements.txt /tmp/
COPY install_browser.sh /tmp/
COPY mpiodijhokgodhhofbcjdecpffjipkle.crx /tmp/

# Install Browsers
RUN /usr/bin/bash /tmp/install_browser.sh

# Install Python dependencies
RUN pip install --upgrade pip -q && \
    pip install -r /tmp/requirements.txt -q

# Clean up unnecessary packages
RUN yum remove -y xz tar unzip bzip2 && \
    yum clean all

# Install shadow-utils and create a non-root user
RUN yum install -y shadow-utils && \
    /usr/sbin/useradd -m lambda_user

# Set the user to the newly created non-root user
USER lambda_user

# Final image with code and dependencies
FROM lambda-base 
RUN whoami
# Copy function code
COPY app.py /var/task/
CMD [ "app.lambda_handler" ]