export interface Department {
  id: string;
  name: string;
  shortName: string;
  slug: string;
  icon: string;
  description: string;
  badge: string;
  categories: string[];
}

export const DEPARTMENTS: Department[] = [
  {
    id: 'incontinencia',
    name: 'Cuidado del Adulto & Incontinencia',
    shortName: 'Incontinencia & Salud',
    slug: 'incontinencia',
    icon: '🩲',
    badge: 'Línea Salud & Residenciales',
    description: 'Pañales para adultos, pants, apósitos indasec/cotidian, sabanillas y artículos de enfermería.',
    categories: [
      'Incontinencia',
      'Medicamentos',
      'Enfermeria',
      'Enfermería / Accesorios Para Medicación',
      'Enfermera / Accesorios Para Medicacin',
    ],
  },
  {
    id: 'limpieza',
    name: 'Limpieza Profesional & Químicos',
    shortName: 'Limpieza & Químicos',
    slug: 'limpieza',
    icon: '🧼',
    badge: 'Línea Química & Institucional',
    description: 'Detergentes de alto rendimiento, desengrasantes, desinfección, lavandería y automotriz.',
    categories: [
      'Limpieza De Pisos',
      'Desengrasantes',
      'Lavado Principal',
      'Prelavado',
      'Suavizado Y Perfumado',
      'Desinfección',
      'Limpieza Profesional',
      'Cocina',
      'Cocina Y Lavavajillas',
      'Baños',
      'Aromatizadores',
      'Limpieza Y Cuidado Automotriz',
      'Siliconas Y Tableros',
      'Inyectores',
      'Aguas Y Refrigeración',
      'Varios',
      'Nuevo',
      'Condimentos',
      'Complementarios',
    ],
  },
  {
    id: 'higiene',
    name: 'Higiene Personal & Papelería',
    shortName: 'Higiene & Papelería',
    slug: 'higiene',
    icon: '🧴',
    badge: 'Línea Descartables & Aseo',
    description: 'Jabones bactericidas, papel higiénico institucional, toallas intercaladas y bolsas de residuos.',
    categories: [
      'Higiene Personal',
      'Artículos Elite – Línea Empresarial',
      'Artculos Elite  Lnea Empresarial',
      'Bolsas Negras',
      'Bolsas Transparentes O Blancas Para Uso De Lavadero',
      'Guantes',
    ],
  },
];

export function getDepartmentForCategory(categoryName: string): Department {
  const norm = categoryName.trim().toLowerCase();
  for (const dept of DEPARTMENTS) {
    if (dept.categories.some((c) => c.toLowerCase() === norm)) {
      return dept;
    }
  }
  // Default to Limpieza si es categoría nueva o no catalogada
  return DEPARTMENTS[1];
}

export function getDepartmentBySlug(slug: string): Department | undefined {
  return DEPARTMENTS.find((d) => d.slug === slug || d.id === slug);
}
