# 3DDesigner

2D形状データを3Dメッシュに変換する独立ツールです。今できるのは単一輪郭から閉じた三角形メッシュを生成し、OBJ/GLBに書き出すことです。ブラウザー画面からFashionDesignerの形状JSONを直接読み込めます。

## 起動方法

Python 3.10以降があれば、追加パッケージ不要です。

```bash
python server.py
```

`http://127.0.0.1:8766/` を開き、FashionDesignerが出力したJSONを選択し、厚みを入力してOBJまたはGLBを書き出します。

## API

`POST /api/mesh?format=glb` または `format=obj`

```json
{"points":[[0,0],[100,0],[100,200],[0,200]],"depth":20,"unit":"mm"}
```

レスポンスはOBJ/GLBのファイルです。不正輪郭、面積ゼロ、自己交差、0以下の厚みは拒否します。サーバーはlocalhostのみで待ち受けます。

## 現在の限界

これは「2D輪郭の押し出し」です。複数の衣服パネル、縫い合わせ、人物寸法への適合、布のたるみやしわ、画像に隠れた面の推定は未実装です。完成した人物・衣服・任意物体の3D化とは扱いません。現在の成果は実ファイルを生成するメッシュ基盤です。

次は共通形状形式にパネル・境界・縫い合わせ関係を定義し、CharacterDesignerの人物形状とFashionDesignerの衣服形状を共通座標で扱い、着装と干渉を検証します。

## 検証

```bash
python -m unittest -v test_mesh_core.py
```

凹形状の三角化と面積、閉メッシュ、外向き体積、OBJ面、GLB header/chunk、無効輪郭を検証します。Blender等での見た目と人物への着装は別途確認が必要です。
