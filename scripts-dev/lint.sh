#!/bin/sh
#
# Runs linting scripts over the local checkout
# isort - sorts import statements
# flake8 - lints and finds mistakes
# black - opinionated code formatter

set -e

if [ $# -ge 1 ]
then
    files=$*
  else
    files="nyx_bot nyx-bot tests"
fi

echo "Linting these locations: $files"
isort $files
flake8 $files
python3 -m black $files
