const euros = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'EUR' })

/** Formats an amount of euros given as a number or as the decimal string that the API sends. */
export function formatEuros(amount: number | string): string {
  return euros.format(Number(amount))
}
