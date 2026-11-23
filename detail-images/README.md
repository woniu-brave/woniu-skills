# Detail Images

从商品资料制作详情页，提供整页视觉参考、可编辑模板、整屏生图和浏览器分屏导出。入口为 [SKILL.md](SKILL.md)。

## 在助手或工作台中使用

1. 保留 `detail-images` 目录和内部结构。按当前助手的导入方式添加 Skill，或在任务里指定读取 `SKILL.md`。
2. 提供商品图、已确认卖点和规格。可以附风格示例，或明确指出需要保留哪份版式的哪些关系。示例请求为「用这款帆布工具包的实拍做八屏详情页，讲清开口、隔层和做工。场景、图标和标注要融入画面。文字你来拟，白底和使用的其他机位也单独给我。」
3. 服装可从 [七屏实拍示范](templates/apparel/index.html) 起步，其他品类可从 [视觉参考库](references/templates.md) 选用逐页模板。完整详情页通常规划 7–14 张，按商品证据组合并逐页导出。复制模板时保留对应 HTML、CSS、脚本与素材的相对位置。

## 本地导出

可在使用 Node.js 20 或以上版本的机器上从此文件夹运行以下命令。已安装的 Chrome 或 Edge 也可以供脚本使用。完整格式和单屏返修见 [制作与导出](references/production.md)。

```text
npm install
npx playwright install chromium
node scripts/export-panels.cjs templates/layouts/craft.html export-craft 750
```

填图样稿使用虚构商品照片。实际制作时用商品原图和已核实资料替换。只有文字工具时可以规划或准备 HTML，带到支持浏览器的机器渲染。
