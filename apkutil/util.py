#!/usr/bin/env python3
# coding: UTF-8

import datetime
import glob
import json
import os
import subprocess
from shutil import move
import shutil
from colorama import Fore


ANDROID_SDK_DEFAULT_PATH = '/Library/Android/sdk/'
ANDROID_HOME = os.environ.get('ANDROID_HOME', ANDROID_SDK_DEFAULT_PATH)

def which_or_fail(cmd_name):
    path = shutil.which(cmd_name)
    if not path:
        raise FileNotFoundError(f"{cmd_name} not found. Please install and make sure it's in PATH.")
    if os.name == 'nt' and not os.path.splitext(path)[1]:
        for ext in ['.cmd', '.bat']:
            if os.path.exists(path + ext):
                return path + ext
    return path

def run_subprocess(cmd, cwd=None):
    is_windows = os.name == 'nt'
    if is_windows and cmd[0].lower().endswith(('.cmd', '.bat')):
        full_cmd = ['cmd.exe', '/c'] + cmd
    else:
        full_cmd = cmd

    proc = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd or os.getcwd()
    )
    outs, errs = proc.communicate()
    return outs.decode('ascii', errors='ignore'), errs.decode('ascii', errors='ignore')

def decode(apk_path, no_res=False, no_src=False):
    apktool_path = which_or_fail('apktool')
    apk_path_abs = os.path.abspath(apk_path)
    dir_path = os.path.splitext(apk_path_abs)[0]

    apktool_cmd = [apktool_path, 'd', apk_path_abs, '-o', dir_path]
    if no_res:
        apktool_cmd.append('-r')
    if no_src:
        apktool_cmd.append('-s')

    try:
        outs, errs = run_subprocess(apktool_cmd)
        if outs:
            print(outs)
        if errs:
            errs = errs.replace('Use -f switch if you want to overwrite it.', '')
            raise Exception(errs)
        return dir_path
    except FileNotFoundError:
        print('apktool not found.')
        print('Please install apktool.')
        return None
    except Exception as e:
        print(str(e))
        return None

def build(dir_name, apk_path, aapt2=False):
    apktool_cmd = [which_or_fail('apktool'), 'b', os.path.abspath(dir_name), '-o', os.path.abspath(apk_path)]
    if aapt2:
        apktool_cmd.append('--use-aapt2')
    try:
        outs, errs = run_subprocess(apktool_cmd)
        if outs:
            if "I: Built apk..." in outs:
                print(outs)
        if errs and "I: Built apk" not in outs:
            raise Exception(errs)
        return True
    except FileNotFoundError:
        print("apktool not found.")
        return False
    except Exception as e:
        print(str(e))
        return False

def align(apk_path):
    try:
        zipalign_path = which_or_fail('zipalign')
        tmp_out = os.path.join(os.path.dirname(apk_path), "apkutil_tmp.aligned.apk")
        zipalign_cmd = [zipalign_path, '-f', '-p', '4', apk_path, tmp_out]
        _, errs = run_subprocess(zipalign_cmd)
        if errs:
            raise Exception(errs)
        move(tmp_out, apk_path)
        return True
    except FileNotFoundError:
        print("zipalign not found.")
        return False
    except Exception as e:
        print(str(e))
        return False

def sign(apk_path):
    home_dir = os.environ.get('HOME', os.environ.get('USERPROFILE', ''))
    try:
        with open(os.path.join(home_dir, "apkutil.json")) as f:
            config = json.load(f)
        keystore_path = config['keystore_path'].replace('~', home_dir)
        ks_key_alias = config['ks-key-alias']
        ks_pass = config['ks-pass']
    except:
        print("Missing or invalid ~/apkutil.json")
        return False

    try:
        if not os.path.isfile(apk_path):
            raise Exception(f"{apk_path} not found.")

        apksigner_path = which_or_fail('apksigner')
        apksigner_cmd = [
            apksigner_path, 'sign',
            '-ks', keystore_path,
            '--v2-signing-enabled', 'true',
            '-v',
            '--ks-key-alias', ks_key_alias,
            '--ks-pass', ks_pass,
            apk_path
        ]
        outs, errs = run_subprocess(apksigner_cmd)
        if outs:
            print(Fore.CYAN + outs)
        if errs:
            print(Fore.RED + errs)
            return False
        return True
    except FileNotFoundError:
        print("apksigner not found.")
        return False
    except Exception as e:
        print(str(e))
        return False

def get_packagename(apk_path):
    try:
        aapt_path = which_or_fail('aapt')
        aapt_cmd = [aapt_path, 'l', '-a', apk_path]
        aapt_proc = subprocess.Popen(aapt_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        grep_proc = subprocess.Popen(['findstr', 'A: package'], stdin=aapt_proc.stdout)
        aapt_proc.stdout.close()
        outs, errs = grep_proc.communicate()
        outs, errs = outs.decode('ascii', errors='ignore'), errs.decode('ascii', errors='ignore')
        if outs:
            print(outs)
        if errs:
            raise Exception(errs)
        return True
    except FileNotFoundError:
        print("aapt not found.")
        return False
    except Exception as e:
        print(str(e))
        return False

def get_screenshot():
    try:
        adb_path = glob.glob(os.path.join(ANDROID_HOME, 'platform-tools', 'adb'))[0]
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
        screenshot_file = f'screenshot-{timestamp}.png'
        screenshot_path = f'/data/local/tmp/{screenshot_file}'

        run_subprocess([adb_path, 'shell', 'screencap', '-p', screenshot_path])
        run_subprocess([adb_path, 'pull', screenshot_path])
        run_subprocess([adb_path, 'shell', 'rm', screenshot_path])

        return screenshot_file
    except (IndexError, FileNotFoundError):
        print("adb not found.")
        return False

def pull_apks(keyword):
    try:
        adb_path = glob.glob(os.path.join(ANDROID_HOME, 'platform-tools', 'adb'))[0]
        package_name = get_package_name(keyword)
        if not package_name:
            print(f"No package found for: {keyword}")
            return False
        apk_paths = get_apk_paths(package_name)
        for apk_path in apk_paths:
            print(f"Pulling {apk_path}...")
            run_subprocess([adb_path, 'pull', apk_path])
        return True
    except:
        print("Error during pull_apks.")
        return False

def get_package_name(keyword):
    adb_path = glob.glob(os.path.join(ANDROID_HOME, 'platform-tools', 'adb'))[0]
    outs, errs = run_subprocess([adb_path, 'shell', 'pm', 'list', 'packages'])
    if errs:
        raise Exception(errs)
    pkgs = [line.split(":")[1] for line in outs.strip().splitlines() if keyword in line]
    return pkgs[0] if pkgs else None

def get_apk_paths(package_name):
    adb_path = glob.glob(os.path.join(ANDROID_HOME, 'platform-tools', 'adb'))[0]
    outs, errs = run_subprocess([adb_path, 'shell', 'pm', 'path', package_name])
    if errs:
        raise Exception(errs)
    return [line.split(":")[1] for line in outs.strip().splitlines()]

def check_sensitive_files(target_path):
    types = ('**/*.md', '**/*.cpp', '**/*.c', '**/*.h', '**/*.java', '**/*.kts',
        '**/*.bat', '**/*.sh', '**/*.template', '**/*.gradle', '**/*.json', '**/*.yml', '**/*.txt')
    allow_list = ('apktool.yml', '/assets/google-services-desktop.json',
        '/assets/bin/Data/RuntimeInitializeOnLoads.json', '/assets/bin/Data/ScriptingAssemblies.json')
    found_files = []
    for file_type in types:
        found_files.extend(glob.glob(os.path.join(target_path, file_type), recursive=True))
    sensitive_files = [f for f in found_files if not any(f.endswith(a) for a in allow_list)]
    if not sensitive_files:
        print(Fore.BLUE + 'None')
    else:
        for f in sensitive_files:
            print(Fore.RED + f)
    return sensitive_files

def make_network_security_config(target_path):
    xml_path = os.path.join(target_path, 'res', 'xml')
    os.makedirs(xml_path, exist_ok=True)
    with open(os.path.join(xml_path, 'network_security_config.xml'), 'w') as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<network-security-config>\n'
            '    <base-config>\n'
            '        <trust-anchors>\n'
            '            <certificates src="system" />\n'
            '            <certificates src="user" />\n'
            '        </trust-anchors>\n'
            '    </base-config>\n'
            '</network-security-config>'
        )
