/** Inline editable SVG primitives; no icon font/CDN dependency. */
export const ICONS={
 book:'<path d="M3 5q5-2 9 2 4-4 9-2v15q-5-2-9 1-4-3-9-1z"/><path d="M12 7v14"/>',
 person:'<circle cx="12" cy="7" r="4"/><path d="M5 22v-4c0-6 14-6 14 0v4z"/>',
 users:'<circle cx="9" cy="7" r="3"/><circle cx="18" cy="8" r="2.5"/><path d="M2 22v-4c0-7 14-7 14 0v4M16 13q7-1 7 5v4"/>',
 room:'<rect x="3" y="3" width="18" height="14" rx="1"/><path d="M8 17v5M16 17v5M7 8h10M7 12h6"/>',
 check:'<rect x="3" y="5" width="18" height="17" rx="2"/><path d="M7 2v6M17 2v6M7 15l4 3 6-7"/>',
 swap:'<path d="M2 7h18l-4-4M22 17H4l4 4M20 7l-4 4M4 17l4-4"/>',
 alert:'<path d="M12 2L1 22h22z"/><path d="M12 8v6M12 18v1"/>',
 cap:'<path d="M1 7l11-5 11 5-11 5zM5 9v8q7 6 14 0V9M23 7v12"/>',
 file:'<path d="M5 2h9l5 5v15H5zM14 2v6h5M8 12h8M8 16h8"/>',
 clock:'<circle cx="12" cy="12" r="10"/><path d="M12 5v7l5 3"/>',
 shield:'<path d="M12 2l9 4v7c0 5-5 8-9 10-4-2-9-5-9-10V6z"/><path d="M7 12l3 3 7-7"/>',
 bars:'<path d="M3 22V12h4v10M10 22V3h4v19M17 22V8h4v14"/>',
 pin:'<path d="M12 23S4 15 4 9a8 8 0 1 1 16 0c0 6-8 14-8 14z"/><circle cx="12" cy="9" r="2.5"/>',
 settings:'<path d="M9 2h6l1 4 4 1 2 5-2 5-4 1-1 4H9l-1-4-4-1-2-5 2-5 4-1z"/><circle cx="12" cy="12" r="4"/>',
 fullscreen:'<path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6"/>',
 refresh:'<path d="M21 9a9 9 0 1 0 0 7M21 2v7h-7"/>',
 back:'<path d="M10 4l-8 8 8 8M2 12h20"/>',
 close:'<path d="M4 4l16 16M20 4L4 20"/>',
 plane:'<path d="M3 5h18v15H3zM3 10h18M9 5v15M15 5v15"/>',
 building:'<path d="M4 22V3h13v19M17 9h5v13M1 22h23M8 7h5M8 11h5M8 15h5M9 22v-3h3v3"/>'
};
export function icon(name,cls='') {return `<svg class="ico ${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]||ICONS.file}</svg>`;}
