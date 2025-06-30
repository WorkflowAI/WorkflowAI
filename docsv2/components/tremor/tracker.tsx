"use client"

import { cn } from "@/lib/cn"
import React from "react"

interface TrackerData {
  tooltip?: string
  color?: string
}

interface TrackerProps extends React.HTMLAttributes<HTMLDivElement> {
  data: TrackerData[]
}

const Tracker = React.forwardRef<HTMLDivElement, TrackerProps>(
  ({ data = [], className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("flex items-center justify-between space-x-0.5", className)}
        {...props}
      >
        {data.map((item, index) => {
          const colorClass = item.color ? `bg-${item.color}` : "bg-gray-200"
          
          return (
            <div
              key={index}
              className={cn(
                "h-2.5 w-2.5 rounded-sm transition-all duration-300 ease-in-out hover:scale-110",
                colorClass
              )}
              title={item.tooltip}
            />
          )
        })}
      </div>
    )
  }
)
Tracker.displayName = "Tracker"

export { Tracker } 