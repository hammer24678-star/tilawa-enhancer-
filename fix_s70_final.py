from pathlib import Path
f = Path('patch_android.py')
txt = f.read_text()
ok = 0; fail = 0

def rep(old, new, lbl):
    global txt, ok, fail
    if old in txt:
        txt = txt.replace(old, new, 1)
        print(f'  OK  {lbl}'); ok += 1
    else:
        print(f'  XX  NOT FOUND — {lbl}'); fail += 1

# ── 1. Setup: download proot package instead of using bundled libproot.so ─────
rep(
    '        progress(1, "Detecting device ($archStr)…")\n'
    '\n'
    '        // 1. proot binary — bundled in APK assets\n'
    '        if (!prootBin.canExecute()) throw Exception("libproot.so not executable")\n'
    '        // Copy libtalloc2.so -> libtalloc.so.2 in filesDir for proot\n'
    '        val tallocSrc = File(context.applicationInfo.nativeLibraryDir, "libtalloc2.so")\n'
    '        val tallocDst = File(dataDir, "libtalloc.so.2")\n'
    '        if (tallocSrc.exists() && !tallocDst.exists())\n'
    '            tallocSrc.copyTo(tallocDst, overwrite = true)\n'
    '\n'
    '        progress(10, "proot ready")',

    '        progress(1, "Detecting device ($archStr)…")\n'
    '\n'
    '        // 1. Download proot + loader from green-green-avk (Android-specific build)\n'
    '        val prootExeFile   = File(dataDir, "proot-pkg/bin/proot")\n'
    '        val loaderFile     = File(dataDir, "proot-pkg/libexec/proot/loader")\n'
    '        if (!prootExeFile.exists() || !loaderFile.exists()) {\n'
    '            progress(2, "Downloading proot for Android…")\n'
    '            val pkgUrl = "https://raw.githubusercontent.com/green-green-avk/build-proot-android/master/packages/proot-android-$archStr.tar.gz"\n'
    '            val pkgFile = File(dataDir, "proot-pkg.tar.gz")\n'
    '            download(pkgUrl, pkgFile, "proot", 2, 9)\n'
    '            progress(9, "Extracting proot…")\n'
    '            val pkgDir = File(dataDir, "proot-pkg").also { it.mkdirs() }\n'
    '            extractTarGz(pkgFile, pkgDir)\n'
    '            pkgFile.delete()\n'
    '            // Package extracts: root/bin/proot, root/libexec/proot/loader\n'
    '            // Move root/* up one level so paths become proot-pkg/bin/proot etc.\n'
    '            val rootSub = File(pkgDir, "root")\n'
    '            if (rootSub.exists()) {\n'
    '                rootSub.listFiles()?.forEach { src ->\n'
    '                    src.copyRecursively(File(pkgDir, src.name), overwrite = true)\n'
    '                }\n'
    '                rootSub.deleteRecursively()\n'
    '            }\n'
    '            prootExeFile.setExecutable(true)\n'
    '            loaderFile.setExecutable(true)\n'
    '            if (!prootExeFile.exists()) throw Exception("proot binary not found after extraction")\n'
    '            if (!loaderFile.exists()) throw Exception("proot loader not found after extraction")\n'
    '        }\n'
    '\n'
    '        progress(10, "proot ready")',
    'setup: download proot package'
)

# ── 2. runProot: use downloaded proot + set PROOT_LOADER ─────────────────────
rep(
    '    private fun runProot(args: List<String>, timeoutMin: Int = 35): Pair<Int, String> {\n'
    '        val cmd = mutableListOf(prootBin.absolutePath,\n'
    '            "--link2symlink",\n'
    '            "-0",\n'
    '            "-r", alpineDir.absolutePath,\n'
    '            "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",\n'
    '                        "-w", "/",\n'
    '            "--kill-on-exit") + args\n'
    '        val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {\n'
    '            environment()["HOME"] = "/root"\n'
    '            environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n'
    '            environment()["TERM"] = "xterm"\n'
    '            environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath\n'
    '            val prootTmp = context.codeCacheDir.also { it.mkdirs() }\n'
    '            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n'
    '            environment()["PROOT_FORCE_KOMPAT"] = "1"\n'
    '        }.start()',

    '    private fun runProot(args: List<String>, timeoutMin: Int = 35): Pair<Int, String> {\n'
    '        val prootExe  = File(dataDir, "proot-pkg/bin/proot").takeIf { it.exists() } ?: prootBin\n'
    '        val loaderExe = File(dataDir, "proot-pkg/libexec/proot/loader")\n'
    '        val cmd = mutableListOf(prootExe.absolutePath,\n'
    '            "--link2symlink",\n'
    '            "-0",\n'
    '            "-r", alpineDir.absolutePath,\n'
    '            "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",\n'
    '            "-w", "/",\n'
    '            "--kill-on-exit") + args\n'
    '        val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {\n'
    '            environment()["HOME"] = "/root"\n'
    '            environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n'
    '            environment()["TERM"] = "xterm"\n'
    '            environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath\n'
    '            val prootTmp = context.codeCacheDir.also { it.mkdirs() }\n'
    '            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n'
    '            environment()["PROOT_FORCE_KOMPAT"] = "1"\n'
    '            if (loaderExe.exists()) environment()["PROOT_LOADER"] = loaderExe.absolutePath\n'
    '        }.start()',
    'runProot: use downloaded proot + PROOT_LOADER'
)

# ── 3. runEngine: use downloaded proot + set PROOT_LOADER ────────────────────
rep(
    '            val cmd = mutableListOf(\n'
    '                prootBin.absolutePath,\n'
    '                "--link2symlink", "-0",\n'
    '                "-r", alpineDir.absolutePath,\n'
    '                "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",\n'
    '                "-b", "${enginesDir.absolutePath}:/engines",\n'
    '                "-b", "${refAudioDir.absolutePath}:/reference_audio",\n'
    '                "-b", "$inParent:$inParent",\n'
    '                "-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}",\n'
    '                "-w", "/", "--kill-on-exit",',

    '            val prootExeEng = File(dataDir, "proot-pkg/bin/proot").takeIf { it.exists() } ?: prootBin\n'
    '            val loaderExeEng = File(dataDir, "proot-pkg/libexec/proot/loader")\n'
    '            val cmd = mutableListOf(\n'
    '                prootExeEng.absolutePath,\n'
    '                "--link2symlink", "-0",\n'
    '                "-r", alpineDir.absolutePath,\n'
    '                "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",\n'
    '                "-b", "${enginesDir.absolutePath}:/engines",\n'
    '                "-b", "${refAudioDir.absolutePath}:/reference_audio",\n'
    '                "-b", "$inParent:$inParent",\n'
    '                "-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}",\n'
    '                "-w", "/", "--kill-on-exit",',
    'runEngine: use downloaded proot'
)

rep(
    '            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {\n'
    '                environment()["HOME"] = "/root"\n'
    '                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n'
    '                environment()["TERM"] = "xterm"\n'
    '            environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath\n'
    '            val prootTmp = context.codeCacheDir.also { it.mkdirs() }\n'
    '            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n'
    '            environment()["PROOT_FORCE_KOMPAT"] = "1"\n'
    '            }.start()',

    '            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {\n'
    '                environment()["HOME"] = "/root"\n'
    '                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n'
    '                environment()["TERM"] = "xterm"\n'
    '                environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath\n'
    '                val prootTmp = context.codeCacheDir.also { it.mkdirs() }\n'
    '                environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n'
    '                environment()["PROOT_FORCE_KOMPAT"] = "1"\n'
    '                if (loaderExeEng.exists()) environment()["PROOT_LOADER"] = loaderExeEng.absolutePath\n'
    '            }.start()',
    'runEngine: PROOT_LOADER env added'
)

f.write_text(txt)
print(f'\n  {ok} OK   {fail} FAIL')
if fail == 0:
    print('  All patches applied — ready to commit')
