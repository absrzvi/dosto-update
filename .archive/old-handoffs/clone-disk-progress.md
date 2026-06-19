Check the status of the in-flight CCU image transfer.

cat IMAGE_TRANSFER_STATUS.md
ls -lh box1-t122-sda-*.img.zst box1-t122-sda-*.exit 2>/dev/null
pgrep -af "ssh.*10.179.122.1" || echo "ssh process not running"
tail -20 nohup.out 2>/dev/null
Then based on what you see:

If .exit file exists: read its contents (expect 0 on success). Then validate the archive:
zstd -t box1-t122-sda-*.img.zst && echo "ARCHIVE OK"
sha256sum box1-t122-sda-*.img.zst | tee box1-t122-sda-*.sha256
Report: archive OK or corrupt, final size, sha256.
If .exit is missing AND ssh process is still running: transfer in flight. Report current output file size, elapsed time since "Started" in the status file, rough estimate of progress (final expected 5–8 GB), and tell me to check back later.
If .exit is missing AND ssh process is gone: transfer died. Report contents of nohup.out, last partial file size, and recommend rerunning Prompt 1.