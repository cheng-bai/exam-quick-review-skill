local function raw(text)
  return pandoc.RawBlock("latex", text)
end

local function has_class(el, class_name)
  for _, value in ipairs(el.classes or {}) do
    if value == class_name then
      return true
    end
  end
  return false
end

function Div(el)
  local begin_env = nil
  local end_env = nil

  if has_class(el, "kami-teacher-answer") then
    begin_env = "\\begin{kamiteacheranswerbox}"
    end_env = "\\end{kamiteacheranswerbox}"
  elseif has_class(el, "kami-teacher-solution") then
    begin_env = "\\begin{kamiteachersolutionbox}"
    end_env = "\\end{kamiteachersolutionbox}"
  elseif has_class(el, "kami-teacher-note") then
    local title = el.attributes["data-title"] or "重点"
    begin_env = "\\begin{kamiteachernotebox}[" .. title .. "]"
    end_env = "\\end{kamiteachernotebox}"
  elseif has_class(el, "kami-teacher-summary") then
    begin_env = "\\begin{kamiteachersummarybox}"
    end_env = "\\end{kamiteachersummarybox}"
  end

  if not begin_env then
    return nil
  end

  local blocks = {raw(begin_env)}
  for _, block in ipairs(el.content) do
    table.insert(blocks, block)
  end
  table.insert(blocks, raw(end_env))
  return blocks
end

local function image_only(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return nil
  end
  if #block.content ~= 1 or block.content[1].t ~= "Image" then
    return nil
  end
  return block.content[1]
end

local function format_factor(value)
  local text = string.format("%.4f", value)
  text = text:gsub("0+$", ""):gsub("%.$", "")
  if text == "" or text == "-" then
    return "0"
  end
  return text
end

local function escape_graphics_path(src)
  return (src:gsub("%%", "\\%%"):gsub("#", "\\#"))
end

-- Pandoc maps a percentage height to \\linewidth or \\textheight depending on
-- version, and drops an unrecognized "0.27\\textheight" attribute back to
-- height=\\textheight. Write the cap explicitly instead.
local function latex_length(value, percent_of)
  if not value or value == "" then
    return nil
  end
  if value:find("\\", 1, true) then
    if value:find("[%{%}%s#&]") then
      return nil
    end
    return value
  end
  local number, unit = value:match("^([%d%.]+)%s*([%a%%]*)$")
  local amount = tonumber(number)
  if not amount or unit == nil then
    return nil
  end
  if unit == "%" then
    return format_factor(amount / 100) .. percent_of
  end
  if unit == "inch" then
    unit = "in"
  end
  if unit == "px" or unit == "" then
    return format_factor(amount / 96) .. "in"
  end
  if unit == "pt" or unit == "cm" or unit == "mm" or unit == "in" or unit == "em" or unit == "pc" then
    return format_factor(amount) .. unit
  end
  return nil
end

function Para(el)
  local image = image_only(el)
  if not image then
    return nil
  end
  local width = latex_length(image.attributes["width"], "\\linewidth")
  local height = latex_length(image.attributes["height"], "\\textheight")
  local width_given = image.attributes["width"] ~= nil and image.attributes["width"] ~= ""
  local height_given = image.attributes["height"] ~= nil and image.attributes["height"] ~= ""
  if (width_given and not width) or (height_given and not height) then
    image.caption = {}
    if not width_given then
      image.attributes["width"] = "58%"
    end
    return {raw("\\begin{center}"), el, raw("\\end{center}")}
  end
  width = width or "0.58\\linewidth"
  height = height or "0.27\\textheight"
  local command = string.format(
    "\\includegraphics[width=%s,height=%s,keepaspectratio]{%s}",
    width,
    height,
    escape_graphics_path(image.src)
  )
  return raw("\\begin{center}\n" .. command .. "\n\\end{center}")
end
