// Leer catálogo oficial, sin confundir fecha de publicación y periodo del fondo.
async function obtenerFichaS4(fondoId) {
  const respuesta = await fetch('./data/factsheets_links.json', {cache:'no-store'});
  if (!respuesta.ok) throw new Error('No se pudo cargar el catálogo de S4');
  const {fondos} = await respuesta.json();
  const registro = fondos.find(f => f.fondo_id === fondoId);
  return registro ? {
    url: registro.url_pdf || null,
    estado: registro.estado,
    periodo: registro.periodo || null,
    fechaDocumento: registro.fecha_documento || null,
    documentacionOriginal: registro.url_ficha_web || registro.url_pagina
  } : null;
}
