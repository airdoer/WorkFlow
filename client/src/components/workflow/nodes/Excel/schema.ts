export interface ExcelConfig {
  /** No more p4Path — content comes from upstream P4File node via input port */
  sheet?: string;
  /** Row filter: selected row indices (1-based) */
  rowFilter?: string[];
  /** Column filter: selected column names */
  columnFilter?: string[];
}
