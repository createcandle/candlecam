#!/bin/bash

for number in {1..9}
do
echo "$number "
ffmpeg -i default.mp3 -af volume=0.0$number default$number.wav
ffmpeg -i classic.mp3 -af volume=0.0$number classic$number.wav
ffmpeg -i business.mp3 -af volume=0.0$number business$number.wav
ffmpeg -i klingel.mp3 -af volume=0.0$number klingel$number.wav
ffmpeg -i fart.mp3 -af volume=0.0$number fart$number.wav
done


for number in {10..100}
do
echo "$number "
ffmpeg -i default.mp3 -af volume=0.$number default$number.wav
ffmpeg -i classic.mp3 -af volume=0.$number classic$number.wav
ffmpeg -i business.mp3 -af volume=0.$number business$number.wav
ffmpeg -i klingel.mp3 -af volume=0.$number klingel$number.wav
ffmpeg -i fart.mp3 -af volume=0.$number fart$number.wav
done
exit 0
