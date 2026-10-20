(() => {
  const assets = new URL('.', document.currentScript.src);
  const initialized = new WeakSet();
  const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
  const formatNumber = new Intl.NumberFormat('en-US');
  let catalogPromise;
  let current;

  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const loadCatalog = () => {
    if (!catalogPromise) {
      catalogPromise = Promise.all([
        fetch(new URL('datasets/catalog.json', assets)).then(response => {
          if (!response.ok) throw new Error('Unable to load the dataset catalog.');
          return response.json();
        }),
        import(new URL('minisearch.js', assets).href),
      ]).then(([catalog, { default: MiniSearch }]) => {
        if (catalog.schema_version !== 1) throw new Error('Unsupported dataset catalog.');
        const search = new MiniSearch({
          idField: 'id',
          fields: ['id', 'name', 'title', 'description', 'authors'],
          extractField: (entry, field) => field === 'authors' ? entry.authors.join(' ') : entry[field],
          searchOptions: {
            prefix: true,
            fuzzy: term => term.length > 3 ? 0.2 : false,
            combineWith: 'AND',
            boost: { id: 8, name: 6, title: 4 },
          },
        });
        search.addAll(catalog.datasets);
        return { entries: catalog.datasets, search };
      }).catch(error => {
        catalogPromise = undefined;
        throw error;
      });
    }
    return catalogPromise;
  };
  const countRange = (dimensions, field) => {
    const values = dimensions.map(dimension => dimension[field]).filter(value => value !== null);
    if (!values.length) return 'Unknown';
    const low = Math.min(...values);
    const high = Math.max(...values);
    return low === high ? formatNumber.format(low) : `${formatNumber.format(low)}–${formatNumber.format(high)}`;
  };
  const size = bytes => {
    if (bytes === null) return 'Unknown';
    for (const [unit, scale] of [['GiB', 1024 ** 3], ['MiB', 1024 ** 2], ['KiB', 1024]]) {
      if (bytes >= scale) return `${(bytes / scale).toLocaleString('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} ${unit}`;
    }
    return `${formatNumber.format(bytes)} B`;
  };

  const initialize = async () => {
    const heading = document.querySelector('main #browse-datasets');
    const table = heading?.nextElementSibling;
    if (table?.tagName !== 'TABLE' || initialized.has(heading)) return;
    initialized.add(heading);
    const status = element('p', 'Loading dataset search…', 'catalog-status');
    status.setAttribute('role', 'status');
    heading.after(status);
    let entries, search;
    try {
      ({ entries, search } = await loadCatalog());
    } catch {
      if (heading.isConnected) status.textContent = 'Search could not load. Browse the table below, or reload the page to try again.';
      initialized.delete(heading);
      return;
    }
    if (!heading.isConnected) return;

    document.querySelector('main').classList.add('catalog-page');
    table.classList.add('catalog-table');
    table.setAttribute('aria-label', 'Dataset search results');
    const form = element('form', undefined, 'catalog-filters');
    form.setAttribute('role', 'search');
    form.setAttribute('aria-label', 'Dataset filters');
    const controls = new Map();
    const field = (label, name, input, parent = form) => {
      const wrapper = element('div', undefined, `catalog-field catalog-field-${name}`);
      const caption = element('label', label);
      input.id = `catalog-${name}`;
      caption.htmlFor = input.id;
      wrapper.append(caption, input);
      input.name = name;
      controls.set(name, input);
      parent.append(wrapper);
      return input;
    };
    const select = (label, name, options, parent) => {
      const input = element('select');
      for (const [value, text] of options) {
        const option = element('option', text);
        option.value = value;
        input.append(option);
      }
      return field(label, name, input, parent);
    };
    const values = key => [...new Set(entries.map(entry => entry[key]))].sort(collator.compare);
    const query = field('Search datasets', 'q', element('input'));
    query.type = 'search';
    query.placeholder = 'Name, topic, or author';
    query.autocomplete = 'off';
    const categories = element('div', undefined, 'catalog-categories');
    form.append(categories);
    select('Source', 'source', [['', 'All sources'], ...values('source').map(value => [value, value])], categories);
    select('Task', 'task', [['', 'All tasks'], ...[...new Set(entries.flatMap(entry => entry.tasks))].sort().map(value => [value, value]), ['unspecified', 'No task specified']], categories);
    select('Representation', 'storage', [['', 'Any'], ...values('storage').map(value => [value, value])], categories);
    select('License', 'license', [['', 'All licenses'], ...values('license').map(value => [value, value])], categories);
    select('Sort by', 'sort', [
      ['relevance', 'Relevance'], ['name', 'Name (A–Z)'],
      ['samples-asc', 'Samples: low to high'], ['samples-desc', 'Samples: high to low'],
      ['predictors-asc', 'Predictors: low to high'], ['predictors-desc', 'Predictors: high to low'],
      ['size-asc', 'Download: small to large'], ['size-desc', 'Download: large to small'],
    ], categories);
    const advanced = element('details', undefined, 'catalog-dimensions');
    advanced.append(element('summary', 'Filter by dimensions'));
    const ranges = element('div', undefined, 'catalog-ranges');
    advanced.append(ranges);
    for (const [name, label] of [
      ['min_samples', 'Minimum samples'], ['max_samples', 'Maximum samples'],
      ['min_predictors', 'Minimum predictors'], ['max_predictors', 'Maximum predictors'],
    ]) {
      const input = field(label, name, element('input'), ranges);
      input.type = 'number';
      input.min = '0';
      input.max = String(Number.MAX_SAFE_INTEGER);
      input.step = '1';
      input.placeholder = 'Any';
      input.inputMode = 'numeric';
    }
    select('Shape', 'shape', [['', 'Any shape'], ['wide', 'More predictors than samples (p > n)']], ranges);
    form.append(advanced);
    const actions = element('div', undefined, 'catalog-actions');
    if (entries.some(entry => !entry.default)) {
      const versions = field('Include other versions', 'versions', element('input'), actions);
      versions.type = 'checkbox';
      versions.parentElement.prepend(versions);
    }
    const reset = element('button', 'Clear filters');
    reset.type = 'reset';
    actions.append(reset);
    form.append(actions);
    heading.after(form);

    const value = name => controls.get(name)?.value || '';
    const number = name => value(name) === '' ? null : Number(value(name));
    const matchingDimensions = entry => entry.dimensions.filter(dimension => {
      if (value('task') && (dimension.type || 'unspecified') !== value('task')) return false;
      for (const field of ['samples', 'predictors']) {
        const min = number(`min_${field}`);
        const max = number(`max_${field}`);
        if (min !== null && (dimension[field] === null || dimension[field] < min)) return false;
        if (max !== null && (dimension[field] === null || dimension[field] > max)) return false;
      }
      return value('shape') !== 'wide' || (
        dimension.predictors !== null && dimension.samples !== null && dimension.predictors > dimension.samples
      );
    });
    const restore = () => {
      const params = new URL(location.href).searchParams;
      for (const [name, input] of controls) {
        const saved = params.get(name) || '';
        if (input.type === 'checkbox') input.checked = saved === '1';
        else if (input.type === 'number') input.value = /^\d+$/.test(saved) && Number(saved) <= Number.MAX_SAFE_INTEGER ? saved : '';
        else if (input.tagName === 'SELECT') input.value = Array.from(input.options).some(option => option.value === saved) ? saved : input.options[0].value;
        else input.value = saved;
      }
      advanced.open = [...controls].some(([name, input]) => (name.startsWith('min_') || name.startsWith('max_') || name === 'shape') && input.value !== '');
    };
    const writeUrl = () => {
      const url = new URL(location.href);
      for (const [name, input] of controls) {
        const saved = input.type === 'checkbox' ? (input.checked ? '1' : '') :
          input.type === 'number' && input.value !== '' ? String(input.valueAsNumber) : input.value;
        if (saved && !(name === 'sort' && saved === 'relevance')) url.searchParams.set(name, saved);
        else url.searchParams.delete(name);
      }
      // The documentation router owns the rest of the history entry.
      history.replaceState(history.state, '', url);
    };
    const render = (updateUrl = true) => {
      if (!form.checkValidity()) {
        status.textContent = 'Enter nonnegative whole numbers for dimensions.';
        return;
      }
      for (const field of ['samples', 'predictors']) {
        if (number(`min_${field}`) !== null && number(`max_${field}`) !== null && number(`min_${field}`) > number(`max_${field}`)) {
          status.textContent = `Minimum ${field} must not exceed maximum ${field}.`;
          return;
        }
      }
      const text = value('q').trim();
      const scores = text ? new Map(search.search(text).map(result => [result.id, result.score])) : null;
      const available = entries.filter(entry => controls.get('versions')?.checked || entry.default);
      const matches = available.filter(entry =>
        (!scores || scores.has(entry.id)) &&
        (!value('source') || value('source') === entry.source) &&
        (!value('storage') || value('storage') === entry.storage) &&
        (!value('license') || value('license') === entry.license) &&
        matchingDimensions(entry).length > 0
      );
      const sortValue = (entry, field) => {
        if (field === 'size') return entry.download_bytes;
        const values = matchingDimensions(entry).map(dimension => dimension[field]).filter(value => value !== null);
        return values.length ? Math.min(...values) : null;
      };
      matches.sort((a, b) => {
        const sort = value('sort');
        if (sort === 'relevance' && scores) {
          const comparison = scores.get(b.id) - scores.get(a.id);
          if (comparison) return comparison;
        } else if (sort !== 'relevance' && sort !== 'name') {
          const [field, direction] = sort.split('-');
          const left = sortValue(a, field), right = sortValue(b, field);
          if (left === null && right !== null) return 1;
          if (right === null && left !== null) return -1;
          const comparison = (left - right) * (direction === 'desc' ? -1 : 1);
          if (comparison) return comparison;
        }
        return collator.compare(a.title, b.title) || collator.compare(a.id, b.id);
      });
      const head = element('thead');
      const header = element('tr');
      for (const title of ['Dataset', 'Source', 'Task', 'Samples', 'Predictors', 'Download', 'License']) {
        const cell = element('th', title);
        cell.scope = 'col';
        header.append(cell);
      }
      head.append(header);
      const body = element('tbody');
      for (const entry of matches) {
        const dimensions = matchingDimensions(entry);
        const row = element('tr');
        const title = element('td');
        const link = element('a', entry.title);
        link.href = entry.url;
        title.append(link, element('span', entry.id, 'catalog-id'));
        row.append(title);
        for (const text of [
          entry.source,
          [...new Set(dimensions.map(dimension => dimension.type || 'No task specified'))].join(', '),
          countRange(dimensions, 'samples'), countRange(dimensions, 'predictors'),
          size(entry.download_bytes), entry.license,
        ]) row.append(element('td', text));
        body.append(row);
      }
      if (!matches.length) {
        const row = element('tr');
        const cell = element('td', 'No datasets match these filters. Try fewer filters or a different search.');
        cell.colSpan = 7;
        row.append(cell);
        body.append(row);
      }
      table.replaceChildren(head, body);
      status.textContent = `${matches.length} of ${available.length} dataset${controls.get('versions')?.checked ? ' versions' : (available.length === 1 ? '' : 's')}`;
      if (updateUrl) writeUrl();
    };
    form.addEventListener('input', () => render());
    form.addEventListener('submit', event => { event.preventDefault(); render(); });
    form.addEventListener('reset', () => { setTimeout(() => { advanced.open = false; render(); }, 0); });
    current = { restore: () => { restore(); render(false); } };
    current.restore();
  };
  document.addEventListener('diplodocus:before-page-change', () => { current = undefined; });
  document.addEventListener('diplodocus:page-change', initialize);
  window.addEventListener('popstate', () => current?.restore());
  initialize();
})();
