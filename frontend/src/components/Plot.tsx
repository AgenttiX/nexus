import type { Data, Layout } from 'plotly.js'
import Plotly from 'plotly.js-basic-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'

const PlotlyPlot = createPlotlyComponent(Plotly)

const INK = '#475569'
const GRID = '#e2e8f0'

const axis = { gridcolor: GRID, linecolor: GRID, zeroline: false, automargin: true }

/** A chart with the house style: recessive grid and axes, no toolbar, hover tooltips. */
export default function Plot({ data, layout, label }: { data: Data[]; layout?: Partial<Layout>; label: string }) {
  return (
    <div role="img" aria-label={label}>
      <PlotlyPlot
        data={data}
        layout={{
          height: 280,
          margin: { t: 8, r: 8, b: 32, l: 48 },
          font: { family: 'inherit', color: INK, size: 12 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          hovermode: 'closest',
          bargap: 0.25,
          legend: { orientation: 'h', y: 1.12, x: 0 },
          ...layout,
          xaxis: { ...axis, ...layout?.xaxis },
          yaxis: { ...axis, ...layout?.yaxis },
        }}
        config={{ displayModeBar: false, responsive: true }}
        useResizeHandler
        style={{ width: '100%' }}
      />
    </div>
  )
}
