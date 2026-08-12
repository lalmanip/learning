#!/usr/bin/env bash
# Improve Jessica Ji Daily Meditation Practice session:
# - Title/outro cards
# - Color grade + denoise
# - Soften harsh Gayatri / meditation overlays
# - MUTE background music during silent meditation (no new music added)
# - Voice clarity + loudness normalize
set -euo pipefail

SRC="/workspace/media/jessica-ji-session-v8.mp4"
OUT_DIR="/workspace/media/out"
ART="/opt/cursor/artifacts"
TITLE="$OUT_DIR/title.png"
OUTRO="$OUT_DIR/outro.png"
FINAL="$OUT_DIR/Daily-Meditation-Practice-Jessica-Ji.mp4"
WORKDIR="$OUT_DIR/work"
mkdir -p "$WORKDIR" "$ART"

SERIF_B="/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"
SERIF="/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf"
SANS="/usr/share/fonts/truetype/macos/Inter-Medium.ttf"

# Silent meditation window (timer ~10:00 → 00:00); music present here — mute it.
MED_START=1272
MED_END=1866

echo "==> [1/4] Processing audio (denoise + mute meditation music)..."
# Mute stereo music during meditation; keep guide voice elsewhere clear and even.
ffmpeg -y -i "$SRC" -vn \
  -af "highpass=f=80,lowpass=f=12000,afftdn=nr=10:nf=-28,\
volume=enable='between(t\,${MED_START}\,${MED_END})':volume=0,\
loudnorm=I=-16:TP=-1.5:LRA=11" \
  -ar 48000 -ac 2 -c:a pcm_s16le "$WORKDIR/audio_clean.wav"

echo "==> [2/4] Building title & outro clips..."
ffmpeg -y -loop 1 -i "$TITLE" -f lavfi -i anullsrc=r=48000:cl=stereo \
  -t 7 -c:v libx264 -pix_fmt yuv420p -r 30 -preset veryfast -crf 18 \
  -c:a aac -b:a 192k -shortest "$WORKDIR/title.mp4"
ffmpeg -y -loop 1 -i "$OUTRO" -f lavfi -i anullsrc=r=48000:cl=stereo \
  -t 6 -c:v libx264 -pix_fmt yuv420p -r 30 -preset veryfast -crf 18 \
  -c:a aac -b:a 192k -shortest "$WORKDIR/outro.mp4"

echo "==> [3/4] Rendering graded main session (this takes a while)..."
# Visual grade: gentle lift, warmth, denoise.
# Overlay refresh:
#  - Gayatri (910–1271): replace harsh yellow bar with soft cream mantra strip
#  - Meditation (1272–1866): replace neon timer/banner with calm UI (NO music)
VF="\
hqdn3d=1.2:1.2:3:3,\
eq=brightness=0.06:contrast=1.06:saturation=1.05:gamma=1.03,\
colorbalance=rs=0.03:gs=0.01:bs=-0.04:rm=0.02:bm=-0.03,\
fps=30,\
drawbox=x=0:y=850:w=1920:h=230:color=0x2a241c@1.0:t=fill:enable='between(t\,910\,1271)',\
drawtext=fontfile=${SERIF}:text='Aum Bhur Bhuvah Swah Tat Savitur Varenyam':fontsize=34:fontcolor=0xf5efe3:x=(w-text_w)/2:y=915:enable='between(t\,910\,1271)',\
drawtext=fontfile=${SERIF}:text='Bhargo Devasya Dhimahi Dhiyo Yo Nah Prachodayat':fontsize=34:fontcolor=0xf5efe3:x=(w-text_w)/2:y=970:enable='between(t\,910\,1271)',\
drawbox=x=0:y=910:w=1920:h=170:color=0x1c2822@1.0:t=fill:enable='between(t\,${MED_START}\,${MED_END})',\
drawbox=x=170:y=690:w=380:h=190:color=0x1c2822@1.0:t=fill:enable='between(t\,${MED_START}\,${MED_END})',\
drawtext=fontfile=${SANS}:fontsize=56:fontcolor=0xd4c4a8:x=250:y=755:enable='between(t\,${MED_START}\,${MED_END})':text='%{eif\\:max(0\\,${MED_END}-t)/60\\:d\\:2}\\:%{eif\\:mod(max(0\\,${MED_END}-t)\\,60)\\:d\\:2}',\
drawtext=fontfile=${SERIF}:text='Silent meditation':fontsize=42:fontcolor=0xf0e6d4:x=(w-text_w)/2:y=970:enable='between(t\,${MED_START}\,${MED_END})'"

ffmpeg -y -i "$SRC" -i "$WORKDIR/audio_clean.wav" \
  -map 0:v:0 -map 1:a:0 \
  -vf "$VF" \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart \
  "$WORKDIR/main.mp4"

echo "==> [4/4] Concatenating title + session + outro..."
printf "file '%s'\nfile '%s'\nfile '%s'\n" \
  "$WORKDIR/title.mp4" "$WORKDIR/main.mp4" "$WORKDIR/outro.mp4" \
  > "$WORKDIR/concat.txt"
ffmpeg -y -f concat -safe 0 -i "$WORKDIR/concat.txt" -c copy "$FINAL"

# Copy deliverable to artifacts
cp -f "$FINAL" "$ART/Daily-Meditation-Practice-Jessica-Ji.mp4"
cp -f "$TITLE" "$ART/title-card.png"
cp -f "$OUTRO" "$ART/outro-card.png"

ffprobe -hide_banner "$FINAL" 2>&1 | head -20
ls -lh "$FINAL" "$ART/Daily-Meditation-Practice-Jessica-Ji.mp4"
echo "DONE: $FINAL"
