(() => {
  const { pageTitle, palette = {}, panels } = window.apparel;
  const main = document.getElementById('pages');
  const layouts = new Set(['cover', 'pair', 'macro', 'split', 'duo', 'color', 'facts']);
  document.title = pageTitle;
  for (const [key, value] of Object.entries(palette)) main.style.setProperty(`--${key}`, value);
  if (document.body.dataset.format === 'square') {
    main.classList.add('square');
    layouts.add('listing');
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function photo({ src, alt, caption, crop, position, fit }) {
    const figure = element('figure', 'figure');
    const frame = element('div', 'photo-frame');
    const image = element('img');
    image.src = src;
    image.alt = alt;
    if (position) image.style.objectPosition = position;
    if (fit === 'contain') image.style.objectFit = fit;
    if (crop) {
      const [sourceWidth, sourceHeight, x, y, width, height] = crop;
      if (width <= 0 || height <= 0 || x < 0 || y < 0 ||
          x + width > sourceWidth || y + height > sourceHeight) {
        throw new Error(`Invalid crop for ${src}`);
      }
      frame.classList.add('cropped');
      frame.style.setProperty('--crop-ratio', `${width} / ${height}`);
      image.style.width = `${sourceWidth / width * 100}%`;
      image.style.height = `${sourceHeight / height * 100}%`;
      image.style.left = `${-x / width * 100}%`;
      image.style.top = `${-y / height * 100}%`;
    }
    frame.append(image);
    figure.append(frame);
    if (caption) figure.append(element('figcaption', '', caption));
    return figure;
  }

  for (const panel of panels) {
    if (!layouts.has(panel.layout)) {
      throw new Error(`Unexpected layout: ${panel.layout}`);
    }
    const section = element('section', `panel ${panel.layout}`);
    if (panel.layout === 'split' && panel.photoSide === 'left') section.classList.add('photo-left');
    section.dataset.exportId = panel.id;
    const heading = element('header', 'heading');
    if (panel.kicker) heading.append(element('p', 'kicker', panel.kicker));
    if (panel.title) heading.append(element(panel.layout === 'cover' ? 'h1' : 'h2', '', panel.title));
    if (panel.note) heading.append(element('p', 'note', panel.note));
    if (heading.childElementCount) section.append(heading);
    if (panel.images?.length) {
      const gallery = element('div', 'photos');
      gallery.append(...panel.images.map(photo));
      section.append(gallery);
    }
    if (panel.facts?.length) {
      const facts = element('dl', 'fact-list');
      for (const [key, value] of panel.facts) {
        facts.append(element('dt', '', key), element('dd', '', value));
      }
      section.append(facts);
    }
    if (panel.footer) section.append(element('p', 'footer', panel.footer));
    main.append(section);
  }
})();
