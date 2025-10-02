#!/bin/bash

# 莆田水费集成发布脚本

VERSION="1.0.0"
ZIP_NAME="putian_water.zip"

echo "正在创建莆田水费集成发布包 v$VERSION..."

# 创建临时目录
mkdir -p release

# 复制必要文件
cp -r custom_components/putian_water/* release/

# 复制文档文件
cp README.md release/
cp info.md release/
cp hacs.json release/

# 创建ZIP包
cd release
zip -r ../$ZIP_NAME ./*

# 清理
cd ..
rm -rf release

echo "发布包创建完成: $ZIP_NAME"
echo "版本: $VERSION"
