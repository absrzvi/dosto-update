Task: Pull a full-disk image of bench CCU 10.179.122.1 (hostname box1-t122) into my workspace as a compressed .img.zst. Wired bench, expected ~5–8 GB output, 1–3 hours. Pre-flight already done by Abbas: sudo passwordless on CCU, sda is 78.7 GB, zstd present. SSH key is ./openssh in this workspace.

You (Claude) do this:

1. Pre-flight (one Bash call):

ls -l openssh && df -h . && \
ssh -i openssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
  developer@10.179.122.1 "hostname && sudo -n true && echo sudo-ok"
Need ≥10 GB workspace free, hostname box1-t122, and sudo-ok. If workspace has <10 GB, stop and tell me — don't launch.

2. Launch the transfer in background, detached so it survives this tool call. Use Bash tool with run_in_background: true:

STAMP=$(date +%Y%m%d-%H%M%S)
nohup bash -c "
  ssh -i openssh -o StrictHostKeyChecking=no \
    developer@10.179.122.1 \
    'sudo dd if=/dev/sda bs=4M | zstd -T0 -3' \
    > box1-t122-sda-${STAMP}.img.zst
  echo \$? > box1-t122-sda-${STAMP}.exit
" > nohup.out 2>&1 &
BGPID=$!
echo "launched PID $BGPID → box1-t122-sda-${STAMP}.img.zst"

cat > IMAGE_TRANSFER_STATUS.md <<EOF
# In-flight CCU image transfer

- **Started:** $(date)
- **Source:** developer@10.179.122.1 (box1-t122), full /dev/sda
- **Output file:** box1-t122-sda-${STAMP}.img.zst
- **Exit marker:** box1-t122-sda-${STAMP}.exit (appears when transfer finishes)
- **Background PID at launch:** ${BGPID}
- **Expected runtime:** 1–3 hours
- **Expected size:** 5–8 GB compressed

To check progress: open a new Claude session and ask "check transfer status" — Claude will read this file, ls the output, look for the .exit marker, and verify the archive if complete.
EOF
3. Report to me:

Pre-flight result (one line summary)
Background PID and output filename
"Transfer running. Come back in 2–3 hours and ask any Claude session to 'check transfer status'."
Don't poll, don't monitor — just kick it off and tell me it's running.