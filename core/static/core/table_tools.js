(function () {
  const normalize = (value) => (value || '').toString().trim();

  const parseSortableValue = (value) => {
    const raw = normalize(value).replace(/\s+/g, ' ');
    const numeric = raw.replace(/R\$|%|\./g, '').replace(',', '.').replace(/[^0-9.-]/g, '');
    if (numeric && !Number.isNaN(Number(numeric))) {
      return { type: 'number', value: Number(numeric) };
    }

    const dateMatch = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (dateMatch) {
      const [, d, m, y] = dateMatch;
      const dateValue = new Date(`${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`).getTime();
      if (!Number.isNaN(dateValue)) return { type: 'number', value: dateValue };
    }

    const isoDate = Date.parse(raw);
    if (!Number.isNaN(isoDate) && /\d/.test(raw)) {
      return { type: 'number', value: isoDate };
    }

    return { type: 'text', value: raw.toLowerCase() };
  };

  const getCellText = (row, index) => {
    const cell = row.cells[index];
    return cell ? normalize(cell.innerText || cell.textContent) : '';
  };

  const enhanceTable = (table, idx) => {
    const headerRow = table.querySelector('thead tr') || table.querySelector('tr');
    if (!headerRow) return;

    const headers = Array.from(headerRow.cells).map((cell, i) => ({
      index: i,
      label: normalize(cell.innerText || cell.textContent) || `Coluna ${i + 1}`,
    }));

    const body = table.tBodies[0] || table;
    const originalRows = Array.from(body.querySelectorAll('tr')).filter((row) => row.cells.length > 1);
    if (!originalRows.length) return;

    const controls = document.createElement('div');
    controls.className = 'table-tools';
    controls.innerHTML = `
      <label>Filtrar
        <input type="search" class="table-tools__search" placeholder="Digite para filtrar..." aria-label="Filtrar tabela">
      </label>
      <label>Ordenar por
        <select class="table-tools__column" aria-label="Escolher coluna para ordenação"></select>
      </label>
      <label>Ordem
        <select class="table-tools__direction" aria-label="Escolher direção de ordenação">
          <option value="asc">Crescente</option>
          <option value="desc">Decrescente</option>
        </select>
      </label>
    `;

    const colSelect = controls.querySelector('.table-tools__column');
    headers.forEach((header) => {
      const option = document.createElement('option');
      option.value = String(header.index);
      option.textContent = header.label;
      colSelect.appendChild(option);
    });

    const searchInput = controls.querySelector('.table-tools__search');
    const directionSelect = controls.querySelector('.table-tools__direction');

    const applyState = () => {
      const query = normalize(searchInput.value).toLowerCase();
      const columnIndex = Number(colSelect.value || 0);
      const direction = directionSelect.value === 'desc' ? -1 : 1;

      const filtered = originalRows.filter((row) => {
        if (!query) return true;
        return normalize(row.innerText || row.textContent).toLowerCase().includes(query);
      });

      filtered.sort((a, b) => {
        const av = parseSortableValue(getCellText(a, columnIndex));
        const bv = parseSortableValue(getCellText(b, columnIndex));
        if (av.value < bv.value) return -1 * direction;
        if (av.value > bv.value) return 1 * direction;
        return 0;
      });

      body.querySelectorAll('tr').forEach((row) => {
        if (row.cells.length > 1) row.style.display = 'none';
      });
      filtered.forEach((row) => {
        row.style.display = '';
        body.appendChild(row);
      });
    };

    searchInput.addEventListener('input', applyState);
    colSelect.addEventListener('change', applyState);
    directionSelect.addEventListener('change', applyState);

    table.parentNode.insertBefore(controls, table);
    colSelect.value = String(Math.min(1, headers.length - 1));
    applyState();
    table.dataset.enhanced = `table-${idx}`;
  };

  document.addEventListener('DOMContentLoaded', () => {
    const tables = Array.from(document.querySelectorAll('table')).filter((table) => !table.dataset.noEnhance);
    tables.forEach((table, idx) => enhanceTable(table, idx));
  });
})();
