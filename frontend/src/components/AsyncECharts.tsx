import { lazy, Suspense } from 'react'
import type EChartsComponent from 'echarts-for-react'

const ReactECharts = lazy(async () => {
  const [{ default: Component }, echarts, charts, components, renderer] = await Promise.all([
    import('echarts-for-react'),
    import('echarts/core'),
    import('echarts/charts'),
    import('echarts/components'),
    import('echarts/renderers'),
  ])
  echarts.use([
    charts.BarChart,
    charts.LineChart,
    charts.PieChart,
    components.GridComponent,
    components.LegendComponent,
    components.TooltipComponent,
    components.TitleComponent,
    components.DataZoomComponent,
    components.DatasetComponent,
    components.TransformComponent,
    renderer.CanvasRenderer,
  ])
  return { default: Component }
})

type Props = React.ComponentProps<typeof EChartsComponent>

const AsyncECharts = (props: Props) => (
  <Suspense fallback={null}>
    <ReactECharts {...props} />
  </Suspense>
)

export default AsyncECharts
