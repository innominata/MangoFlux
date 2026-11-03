# MangoFlux

A local Windows and Linux desktop app for removing manga lettering with FLUX 3 Image Klein. The original page is never overwritten. The model regenerates the page and may change artwork, borders, or fine details; inspect the result before using it.

## Start

### Windows

1. Extract all files into a folder and double-click `MangoFlux.cmd`. On first launch it downloads an official, signature-verified Python 3.12 runtime into `%LOCALAPPDATA%\MangoFlux`. The initial launcher needs internet access; no Python installation or command line is required.
2. Select **CPU**, **CUDA** (NVIDIA), **ROCm** (compatible AMD), or **Vulkan** (compatible Intel and other GPUs) and choose **Install runtime**. Vulkan support is experimental and selects Vulkan device 0, which might not be the Intel GPU on a multi-GPU system. Check the runtime log for the selected device. A compatible up-to-date graphics driver is required.
3. Open the model license, sign in to Hugging Face and accept its conditions. Create a read token, paste it into the app, and choose **Download model**. The app saves it encrypted with Windows Data Protection for your Windows account and reloads it next time. Choose **Forget token** to delete it. Downloads can be retried after interruption.
4. Open an image, choose a mode, and click **Clean**. Compare the previews and save a PNG. Auto mode uses the same crop approach as Komatose; tiled results can have seams and lose context. Whole-page mode downsizes images above 4 megapixels before processing and restores their pixel dimensions afterward.

### Linux (Omarchy / Arch)

The provided prebuilt runtimes target x86-64 Linux and are built for Ubuntu 24.04; compatibility with Arch/Omarchy and its installed libraries is not guaranteed. Make sure Python is installed, then run `bash MangoFlux.sh` from the extracted app directory. The launcher checks for Tk and installs it if missing using pacman, apt-get, dnf, or zypper, requesting your sudo password when needed. On other distributions, install Tk support for Python manually. The launcher creates an isolated environment under `${XDG_DATA_HOME:-~/.local/share}/MangoFlux` without changing system Python.

Select **ROCm** for compatible AMD cards and install the runtime. The runtime requires a compatible ROCm 10.1 stack and GPU driver; the app does not install drivers. If the ROCm build cannot load its shared libraries or find the GPU, try **Vulkan** with an installed Vulkan driver (on Arch, `vulkan-radeon` for AMD). **CPU** is also available. The packaged Linux release does not include CUDA; NVIDIA users can use Vulkan. See [AMD's compatibility matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/native_linux/native_linux_compatibility.html) for officially supported platforms.

Use **List devices** after runtime setup, then enter the desired GPU index. A job uses one selected GPU; multiple cards do not combine their memory automatically. Use the same license, model download and page-cleaning steps as on Windows.

For token persistence install `libsecret` and use an unlocked Secret Service keyring (such as GNOME Keyring or KWallet). If no keyring is available, the token stays in the app only for the current session; it is never saved as plaintext.

The app downloads the same Q8 GGUF transformer and Q8 GGUF text encoder used by Komatose (about 10.7 GB total), plus the autoencoder. Allow at least 40 GB free disk space for downloads, runtime and caches, plus substantial system RAM. The private stable-diffusion.cpp runtime uses CPU offloading on GPU backends to reduce VRAM demands; CPU inference can take a very long time. Q8 does not guarantee a fit on every 8 GB GPU: memory depends on image dimensions, hardware and runtime. Downloads, loading, and inference can take a long time. Setup activity appears in the app; Cancel terminates the active process.

The exact requested prompt is sent directly to the distilled model without the additional prompt upsampler. The app uses Komatose's Q8 model files and its stable-diffusion.cpp edit endpoint with 16 Euler steps, CFG 1, and full strength. In tiled mode it uses 768-pixel cores and 128-pixel context, processing the entire page as selected.

Intel integrated GPUs share system RAM with the CPU. On Windows, Vulkan mode streams weights from disk and limits its GPU budget to 4 GiB to leave room for other allocations. This can be slow, and sufficient free system memory is still necessary. Performance and driver compatibility vary. This app does not currently support Intel NPUs.

Remove weights through **Remove model**. To remove all app-managed data, close the app and double-click `Remove MangoFlux Data.cmd`; then delete the app folder. No system-wide packages or drivers are installed by the app. The launcher uses the official Python installer in a private target directory and does not modify PATH.

FLUX 3 Image Klein is subject to the [FLUX Kommunity License](https://huggingface.co/black-forest-labs/flux-3-image-klein). The model and dependencies are downloaded from their respective publishers and are not bundled in this app.
