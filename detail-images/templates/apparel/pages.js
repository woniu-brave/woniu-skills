const sampleAssets = '../../assets/';
const samplePhoto = (name, alt, caption) => ({ src: sampleAssets + name, alt, caption });

window.apparel = {
  pageTitle: '雾玫瑰绒织开衫｜服装详情示范',
  palette: { paper: '#f6efe9', ink: '#402e35', tint: '#e8d2cf', dark: '#49373c', accent: '#ac6e60' },
  panels: [
    { id: 'cover', layout: 'cover', kicker: '绒织开衫', title: '雾玫瑰\n轻织开衫', note: '浅色圆扣沿门襟排开，留一点复古感。', images: [samplePhoto('craft-a.svg', '穿雾玫瑰开衫的模特')] },
    { id: 'shape', layout: 'pair', title: '平铺看版型\n侧身看袖量', images: [samplePhoto('craft-b.svg', '开衫正面平铺', '平铺正面'), samplePhoto('craft-d.svg', '开衫上身侧后角度', '上身侧面')] },
    { id: 'texture', layout: 'macro', title: '近看颗粒织纹', note: '织纹在光线下有细微起伏。', images: [samplePhoto('craft-c.svg', '针织纹理近照')] },
    { id: 'opening', layout: 'split', title: '同排浅色圆扣', note: '圆形扣面沿前襟排布。', images: [samplePhoto('craft-c.svg', '前襟圆扣和针织面料')] },
    { id: 'sleeves', layout: 'duo', title: '从肩线到袖口', images: [samplePhoto('craft-d.svg', '模特侧面的肩袖', '侧身袖型'), samplePhoto('craft-b.svg', '开衫的平铺长袖', '平铺袖长')] },
    { id: 'color', layout: 'color', title: '雾玫瑰', note: '暖调粉色，配一排浅色小圆扣。', images: [samplePhoto('craft-b.svg', '雾玫瑰色实物示意')] },
    { id: 'facts', layout: 'facts', title: '款式一览', facts: [['品名', '雾玫瑰绒织开衫'], ['色名', '雾玫瑰'], ['领型', '圆领'], ['开合', '前襟圆扣']], footer: '版式示范 · 虚构商品资料' }
  ]
};
