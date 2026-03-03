// This project was developed with assistance from AI tools.

import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { cn } from "../../../lib/utils"
import { badgeVariants } from "./badge-variants"

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export { badgeVariants } from "./badge-variants"
