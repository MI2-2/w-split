# -*- coding:utf-8 -*-
import os, sys, shutil, subprocess, tempfile, re, time, unicodedata, configparser, glob
from concurrent import futures
from PIL import Image   # pillow インストール必要
import pillow_avif      # pillow-avif-plugin インストール必要
import cv2              # opencv-python インストール必要
import numpy as np      # numpy インストール必要
from send2trash import send2trash # send2trash インストール必要
from winsort import winsort # 自作モジュール導入必要

import logging
logging.basicConfig(level=logging.INFO)

# 並行処理のための、トリミング関数
def page_crop(p):
    logging.debug('start_proc')
    with Image.open(os.path.join(tpath, p)) as img:
        # トリミング値の計算
        width, height = img.size
        br = ((width/2), 0, (width*(1-rlTrim)), height)  # 右ページ
        bl = ((width*rlTrim), 0, (width/2), height)      # 左ページ
        # 右ページトリミング
        new_pr = img.crop(br)
        if os.path.splitext(p)[1] == '.png':
            new_pr = new_pr.convert('RGB')
        new_pr_name = os.path.splitext(p)[0] + '_1.jpg'
        new_pr.save(os.path.join(new_img_path, new_pr_name))
        # 左ページトリミング
        new_pl = img.crop(bl)
        if os.path.splitext(p)[1] == '.png':
            new_pl = new_pl.convert('RGB')
        new_pl_name = os.path.splitext(p)[0] + '_2.jpg'
        new_pl.save(os.path.join(new_img_path, new_pl_name))
    logging.debug('end_proc')

# jpg への変換関数
def png_conv(p):
    logging.debug('start_proc')
    with Image.open(os.path.join(tpath, os.path.basename(p))) as conv_image:
        conv_image = conv_image.convert('RGB')
        conv_image.save(os.path.join(new_img_path, os.path.splitext(os.path.basename(p))[0] + '.jpg'))
    logging.debug('end_proc')

# 余白の自動検出
def mergin(pic, pos):
    # openCVは2バイト文字を扱えないので、pillowで読み込み閾値の算出にのみopenCVを利用する。
    with Image.open(pic) as img0:
        # 画像サイズ取得
        width, height = img0.size
        # グレースケールに変換
        img_gray = img0.convert('L')
    # 座標(0,0)の階調を取得(グレースケールなので1ch)
    g = img_gray.getpixel((0,0))
    # numPyに突っ込みopenCVで扱えるndarrayにする。
    img_n = np.array(img_gray)
    # 閾値の算出(大津メソッド)
    threshold, _ = cv2.threshold(img_n, 0, 255, cv2.THRESH_OTSU)
    # watermark避けで画像の上2/3だけ採用
    img_n = img_n[0:height*2//3, 0:width] 
    # 閾値より大きければ余白は'白'、小さければ'黒'と判定し、
    # 余白が白なら黒の最小・最大x座標を、黒なら白の最小・最大x座標を求める。
    if g >= threshold:   # 余白は白
        coord = np.where(img_n < threshold)   #黒部分の座標を求める
    elif g < threshold:  # 余白は黒
        coord = np.where(img_n >= threshold)  #白部分の座標を求める
    coord_min = min(coord[1])
    coord_max = max(coord[1])
    # 表紙の余白座標から、余白のトリミング量を計算
    if pos == 'c':
        rlTrim = ((4 * coord_min - width) / 2) / width
#        rlTrim = ((3 * width - 4 * coord_max) / 2) / width
    elif pos == 'l':
        rlTrim = coord_min / width
    elif pos == 'r':
        rlTrim = (width - coord_max) / width
    else:
        pass
    # トリム量を返す
    return rlTrim


if __name__ == '__main__':

    # iniファイルから設定値読み込み
    inipath = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'w-split.ini')
    ini = configparser.ConfigParser()
    if os.path.isfile(inipath):
        ini.read(inipath, 'UTF-8')
        # 画像の再確認
        confirm = int(ini['global']['confirm'])
        # 7zipの場所
        z7 = ini['global']['7zpass']
        if not os.path.isfile(z7):
            print('7zipがありません')
            sys.exit()
    else:
        print('w-split.ini を w-split.exe と同じフォルダーにおいてください')
        input()
        sys.exit()

    # 処理ファイル名を引数から受け取り
    files = sys.argv

    # 引数なしならエラー
    if len(files) == 1:
        print('引数を指定してください')
        input()
        sys.exit()

    for file in files[1:]:

        print(os.path.basename(file) + ' 処理中...')

        # 作業用一時フォルダの作成
        with tempfile.TemporaryDirectory() as tempdir:

            # 処理対象がファイルのときの処理
            if os.path.isfile(file):

            # ファイル名、パス名の定義
                fname = os.path.splitext(os.path.basename(file))[0]     # 元ファイル名、拡張子なし
                path = os.path.dirname(file)                            # 元ファイルのあるフォルダ名
                ppath = os.path.join(path, fname)                       # 新しいフォルダ名
                tpath = os.path.join(tempdir, fname)                    # 作業用一時フォルダ名

                # 解凍先フォルダの作成
                if not os.path.isdir(tpath):
                    os.makedirs(tpath)

                # 7zipで書庫展開(フォルダ構造なし、フラット展開)
                print('書庫展開中...')
                subprocess.run([z7, 'e', file, '-y', '-bd', '-o' + tpath], stdout=subprocess.DEVNULL)
                # フォルダーを検索
                list_dirs = next(os.walk(tpath))[1]
                # サブフォルダが複数あったらエラー
                if len(list_dirs) > 1:
                    print('フォルダが二重もしくは複数あります')
                    print('前処理が必要です')
                    print('スキップ')
                    print()
                    continue
                # サブフォルダが1つならそのフォルダー名を新規ファイル名として採用
                elif len(list_dirs) == 1:
                    fname = list_dirs[0]

            # 処理対象がフォルダのときの処理
            elif os.path.isdir(file):

                # ファイル名、パス名の定義
                fname = os.path.basename(file)                          # 元フォルダ名
                path = os.path.dirname(file)                            # 元ファイルのあるフォルダ名
                ppath = file                                            # 新しいフォルダ名
                tpath = os.path.join(tempdir, fname)                    # 作業用一時フォルダ名

                # 一時作業フォルダに全ファイルをコピー
                os.mkdir(tpath)
                pic_files = os.listdir(file)
                for pic_file in pic_files:
                    shutil.copy(os.path.join(file, pic_file), tpath)

            # これ以降ファイル、フォルダ共通処理

            # ファイル名の置換。なぜか100ページ以降"_"が"-"になってるファイル対策
            # 大文字→小文字置換。なぜか100ページ以降一部大文字になってるファイル対策
            for f in next(os.walk(tpath))[2]:
                f_old = os.path.join(tpath, f)
                f_new = f.replace('-', '_').lower()
                newname = os.path.join(tpath, f_new)
                os.rename(f_old, newname)

            list_files = next(os.walk(tpath))[2]
            # 二重書庫チェック
            l_in = [l for l in list_files if '.rar' in l or '.zip' in l]
            if len(l_in) > 0:
                print('2重書庫ファイルです')
                print('スキップ')
                print()
                continue

            # 不要ファイルの削除
            for f in list_files:
                # 削除対象ファイルの削除
                ext = ini['global']['ExcludeFile']
                if re.search(ext, f):
                    os.remove(os.path.join(tpath, f))
                    print(f + ' を削除')
                # cover のリネーム
                if os.path.splitext(os.path.basename(f))[0] == 'cover':
                    cover = os.path.join(tpath, '00000' + os.path.splitext(f)[1])
                    if not os.path.isfile(cover):
                        os.rename(os.path.join(tpath, f), cover)

            # 一時フォルダのファイルリスト

            all_pics = next(os.walk(tpath))[2]

            # windowsのexplorerライクソート
            all_pics = winsort(all_pics)

            # エクスプローラ起動、待ち
            subprocess.Popen(['explorer', tpath], shell=True)
            print('画像の余白を確認後エクスプローラーを閉じてください。')

            print('新ファイル名: ' + fname)

            # 分割方法と表紙位置の選択
            isPage = False
            while not isPage:
                try:
                    tpage = int(input('表紙: 中央:1 / 右:2 / 左:3 / _*.*:4 / 置換:5 / 分割無:8 / スキップ:9 / 中断:0  ?:'))
                    if tpage in [1, 2, 3, 4, 5, 8, 9, 0]:
                        isPage = True
                except ValueError:
                    continue
            if tpage == 9:
                continue
            elif tpage == 0:
                sys.exit()
            elif tpage in [4, 5]:
                isPage = False
                while not isPage:
                    try:
                        tpage2 = int(input('表紙: 中央:1 / 右:2 / 左:3  ?:'))
                        if tpage2 in [1, 2, 3]:
                            isPage = True
                    except ValueError:
                        continue
            else:
                tpage2 = ''

            # ファイル名の再取得
            all_pics = next(os.walk(tpath))[2]
            all_pics = winsort(all_pics)

            # トリム量の決定
            if tpage in [1, 2, 3, 4, 5]:
                isNum = False
                while not isNum:
                    try:
                        trim = int(input('余白削除(自動):1 / 余白なし:2 / 余白固定値({:.1f}%):3 / 余白指定:4 / スキップ:9 / 中断:0  :?'.format(float(ini['global']['trim']))))
                        if trim in [1, 2, 3, 4, 9, 0]:
                            isNum = True
                    except ValueError:
                        continue
            if tpage == 9:
                continue
            elif tpage == 0:
                sys.exit()
            else:
                pass

            if not tpage == 8:
                if trim == 1:
                    if tpage == 1 or tpage2 == 1:   # 表紙中央
                        rlTrim = mergin(os.path.join(tpath, all_pics[0]), 'c')
                        print('トリミング量: {:.2f}%'.format(rlTrim * 100))
                    elif tpage == 2 or tpage2 == 2: # 表紙右
                        rlTrim = mergin(os.path.join(tpath, all_pics[0]), 'r')
                        print('トリミング量: {:.2f}%'.format(rlTrim * 100))
                    else:                           # 表紙左
                        rlTrim = mergin(os.path.join(tpath, all_pics[0]), 'l')
                        print('トリミング量: {:.2f}%'.format(rlTrim * 100))
                elif trim == 3:
                    rlTrim = float(ini['global']['trim'])/100
                elif trim == 4:
                    rlTrim = float(input('余白(0～20)[%] = '))/100
                else:
                    rlTrim = 0

                if rlTrim < 0 or rlTrim > 0.2:
                    print('トリム値エラー(0～20%以外)')
                    print('スキップ')
                    continue

            # トリミングした画像を保存するフォルダ
            new_img_path = os.path.join(tpath, 'trim', 'pics')
            #もし存在しなければ作る
            if not os.path.isdir(new_img_path):
                os.makedirs(new_img_path)
            
            # 分割なしならただ移動、png,avifはjpgに変換、画像確認はなし
            if tpage == 8:
                cov_pics = glob.glob(glob.escape(tpath) + '/*.png') + glob.glob(glob.escape(tpath) + '/*.avif')
                cov_pics = [os.path.basename(f) for f in cov_pics]
                jpg_pics = list(set(all_pics) - set(cov_pics))
                if len(cov_pics) != 0:
                    print('画像変換中...')
                    print('※画像確認なし')
                    with futures.ThreadPoolExecutor() as executor:
                        result = executor.map(png_conv, cov_pics)
                if len(jpg_pics) != 0:
                    for jpg in jpg_pics:
                        shutil.move(os.path.join(tpath, jpg), new_img_path)

            # 先頭のみ分割の場合、分割対象を(_*.*)に絞り残りはコピー
            elif tpage == 4:
                trim_pics = glob.glob(glob.escape(tpath) + '/_*.*')
                trim_pics = [os.path.basename(p) for p in trim_pics]
                if len(trim_pics) == 0:
                    print('_*.* ファイルがありません')
                    continue
                with Image.open(os.path.join(tpath, trim_pics[0])) as img0:
                    width, height = img0.size
                    if tpage2 == 1:      # 表紙センター
                        box = ((width*(2*rlTrim+1)/4), 0, (width*(1-(2*rlTrim+1)/4)), height)
                    elif tpage2 ==2:    # 表紙右ページ
                        box = ((width/2), 0, (width*(1-rlTrim)), height)
                    elif tpage2 == 3:    # 表紙左ページ
                        box = ((width*rlTrim), 0, (width/2), height)
                    new_img_c = img0.crop(box)
                    if os.path.splitext(trim_pics[0])[1] == '.png':
                        new_img_c = new_img_c.convert('RGB')
                    new_img_name_c = os.path.splitext(trim_pics[0])[0] + '_0.jpg'
                    new_img_c.save(os.path.join(new_img_path, new_img_name_c))
                with futures.ThreadPoolExecutor() as executor:
                    result = executor.map(page_crop, trim_pics[1:])
                rest_pics = list(set(all_pics) - set(trim_pics))
                if len(rest_pics) != 0:
                    for pic in rest_pics:
                        shutil.move(os.path.join(tpath, pic), new_img_path)
                if confirm != 0:
                    subprocess.Popen(['explorer', new_img_path], shell=True)
                    print('画像を確認後エクスプローラーを閉じてください')

            # 通常分割なら分割、トリミング
            elif tpage in [1, 2, 3]:
                start_time = time.perf_counter()
                print('トリミング中...')
                # 先頭ページトリミング
                with Image.open(os.path.join(tpath, all_pics[0])) as img0:
                    width, height = img0.size
                    if tpage == 1:      # 表紙センター
                        box = ((width*(2*rlTrim+1)/4), 0, (width*(1-(2*rlTrim+1)/4)), height)
                    elif tpage == 2:    # 表紙右ページ
                        box = ((width/2), 0, (width*(1-rlTrim)), height)
                    else:               # 表紙左ページ
                        box = ((width*rlTrim), 0, (width/2), height)
    
                    new_img_c = img0.crop(box)
                    if os.path.splitext(all_pics[0])[1] == '.png':
                        new_img_c = new_img_c.convert('RGB')
                    new_img_name_c = os.path.splitext(all_pics[0])[0] + '_0.jpg'
                    new_img_c.save(os.path.join(new_img_path, new_img_name_c))

                # 2ページ以降トリミング、平行処理
                with futures.ThreadPoolExecutor() as executor:
                    result = executor.map(page_crop, all_pics[1:])

                end_time = time.perf_counter()
                elapsed_time = '{:.2f}'.format(end_time - start_time)
                logging.debug('所要時間: ' + str(elapsed_time) + '[sec]')

                # エクスプローラ起動、待ち
                if confirm != 0:
                    subprocess.Popen(['explorer', new_img_path], shell=True)
                    print('画像を確認後エクスプローラーを閉じてください')

            # 分割元画像との置換の場合
            elif tpage == 5:
                # 分割対象のリスト
                pic_files = os.listdir(file)
                with Image.open(os.path.join(tpath, pic_files[0])) as img0:
                    width, height = img0.size
                    if tpage2 == 1:      # 表紙センター
                        box = ((width*(2*rlTrim+1)/4), 0, (width*(1-(2*rlTrim+1)/4)), height)
                    elif tpage2 == 2:    # 表紙右ページ
                        box = ((width/2), 0, (width*(1-rlTrim)), height)
                    elif tpage2 == 3:    # 表紙左ページ
                        box = ((width*rlTrim), 0, (width/2), height)
    
                    new_img_c = img0.crop(box)
                    if os.path.splitext(all_pics[0])[1] == '.png':
                        new_img_c = new_img_c.convert('RGB')
                    new_img_name_c = os.path.splitext(all_pics[0])[0] + '_0.jpg'
                    new_img_c.save(os.path.join(new_img_path, new_img_name_c))

                # 2ページ以降トリミング、平行処理
                with futures.ThreadPoolExecutor() as executor:
                    result = executor.map(page_crop, pic_files[1:])
                # 元画像を削除
                for pic_file in pic_files:
                    send2trash(os.path.join(file, pic_file))
                # トリミング画像を元フォルダにコピー
                new_pics = os.listdir(new_img_path)
                for pic in new_pics:
                    shutil.copy(os.path.join(new_img_path, pic), os.path.splitext(file)[0])
                continue

            else:
                pass

            isKaku = False
            while not isKaku:
                try:
                    kakunin = int(input('1: (一般コミック) / 2: (少女漫画) / 3: 追加なし / 9: スキップ / 0: 中断  ?:'))
                    if kakunin in [1, 2, 3, 9, 0]:
                        isKaku = True
                except ValueError:
                    continue
            if kakunin == 9:
                continue
            elif kakunin == 0:
                sys.exit()

            # トリミングファイルを自然順ソートしてリネーム
            new_pics = winsort(os.listdir(new_img_path))
            i = 0
            for pic in new_pics:
                # 数値を三桁(000)形式にそろえる
                zero_i = '{0:03d}'.format(i)
                num_name = zero_i + os.path.splitext(pic)[1]
                num_name = os.path.join(new_img_path, num_name)
                old_name = os.path.join(new_img_path, pic)
                os.rename(old_name, num_name)
                i += 1

            # フォルダ削除、trimフォルダリネーム
            if os.path.isdir(os.path.join(tpath, 'trim', fname)):
                shutil.rmtree(os.path.join(tpath, 'trim', fname))
            os.rename(new_img_path, (os.path.join(tpath, 'trim', fname)))

            # 元ファイルはゴミ箱に
            if os.path.isfile(file):
                send2trash(file)

            # zip書庫に圧縮
            print('書庫圧縮中...')
            zip_name = os.path.join(path, fname)
            zip_dir = os.path.join(tpath, 'trim', fname)
            subprocess.run([z7, 'a', '-tzip', zip_name, zip_dir], stdout=subprocess.DEVNULL)
#            shutil.make_archive(os.path.join(path, fname), format='zip', root_dir=os.path.join(tpath, 'trim'), base_dir=fname)

            # ファイル名整形、付加
            if kakunin == 1:
                add = '(一般コミック) '
            elif kakunin == 2:
                add = '(少女漫画) '
            else:
                add = ''
            new_name = re.sub('^\(.*\) ', '', os.path.basename(fname))
            new_name = add + new_name + '.zip'
            # 文字列の正規化
            new_name = unicodedata.normalize('NFKC', new_name)
            # 文字列の置換
            new_name = re.sub(r'\[[^\]]*\]', lambda m: m[0].replace('x', '×'), new_name)
            new_name = new_name.replace('_', ' ').replace('!', '！').replace(':', '：').replace('/', '／').replace('?', '？').replace('<', '＜').replace('>', '＞').replace('~', '～').replace('卷', '巻')

            if not os.path.isfile(new_name):
                try:
                    os.chdir(path)
                    os.rename(fname + '.zip', new_name)
                except Exception as e:
                    print(e)
            else:
                print('同名ファイルが存在しています')

        os.chdir(path)
        if os.path.isdir(file):
            try:
                send2trash(file)
            except Exception:
                time.sleep(0.1)
#                shutil.rmtree(file)
                subprocess.run('cmd /c rmdir /s /q "' + file + '"')
        print('')

    else:
        print('処理終了')
        sys.exit()