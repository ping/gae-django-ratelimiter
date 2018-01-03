#!/usr/bin/env bash

set -e

# Source: https://blog.bekt.net/p/gae-sdk/
API_CHECK='https://appengine.google.com/api/updatecheck'
SDK_VERSION=$(curl -s $API_CHECK | awk -F '\"' '/release/ {print $2}')
# Remove the dots.
SDK_VERSION_S="${SDK_VERSION//./}"

SDK_URL='https://storage.googleapis.com/appengine-sdks/'
SDK_URL_A="${SDK_URL}featured/google_appengine_${SDK_VERSION}.zip"
SDK_URL_B="${SDK_URL}deprecated/$SDK_VERSION_S/google_appengine_${SDK_VERSION}.zip"

function download_sdk {
    echo ">>> Downloading... GAE ver $SDK_VERSION"
    mkdir -p gae_sdk
    curl -L -s --fail -o "gae.zip" "$SDK_URL_A" || \
        curl -L --fail -s -o "gae.zip" "$SDK_URL_B" || \
        exit 1
    unzip -qd gae_sdk "gae.zip" && rm gae.zip
}

download_sdk
