#!/usr/bin/env python3
"""
PIFRS MCP Server - Optimized for macOS
Personal file assistant for finding and organizing files by timestamps, names, and content.
Author: Siddarth Singaravel
"""

from mcp.server.fastmcp import FastMCP
import os
from datetime import datetime, timedelta
from pathlib import Path
import json
from collections import defaultdict
import mimetypes
from functools import lru_cache

#Initializing my MCP server with my personalized name 
mcp =FastMCP("PIFRS-Personal Intelligent File Retrieval System")

#<-------------------------- Setting up the constants ----------------------------->
NOTES_FILE=os.path.expanduser("~/notes.txt")

#Limits larger outputs
MAX_FILE_RESULTS =50

#This limits how deep the search goes into subdirectories to prevent long runtimes on large filesystems
MAX_SEARCH_DEPTH =10 

#Common directories to skip for faster search on Mac
COMMON_DIRS_TO_SKIP={'.git','.svn','node_modules','__pycache__','.DS_Store','Library','.Trash'} 
LIST_OF_TEXT_EXTENSIONS={'.txt','.md','.py','.js','.json','.xml','.html','.css','.yaml','.yml','.ini','.conf','.log','.csv','.sql','.sh','.c','.cpp','.h','.java','.rb','.php','.go','.rs','.swift'}

#Helper function to ensure notes file exists
def ensure_file():
    """Creates notes file if it doesn't exist-prevents errors during append operations"""
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE,"w") as f:
            f.write("")

#Caching result to speed up repeated checks on the same paths
@lru_cache(maxsize=64)
def check_if_valid_path_exists(path_str:str)->bool:
    """Check if path exists and is accessible -cached for performance"""
    try:
        path =Path(path_str)
        return path.exists() and os.access(path,os.R_OK)
    except:
        return False

#Helper to check if directory should be skipped for faster search
def should_skip_dir(dir_name:str)->bool:
    """Skip common Mac system directories and hidden folders to speed up search"""
    return dir_name.startswith('.') or dir_name in COMMON_DIRS_TO_SKIP


#Helper to check if file is a text file based on extension -used for content search and reading
@mcp.tool()
def add_note(message:str)->str:
    """
    Add a new note to your notes file.
    Args: message - The note content to be added
    Returns:Confirmation message
    Example:add_note("Remember to review the quarterly report")
    """
    ensure_file()
    with open(NOTES_FILE,"a") as f: #Append mode preserves existing notes
        f.write(message+"\n")
    return "Notes Saved Successfully at Mac!!"

@mcp.tool()
def find_recent_files(days_ago:int=7,root_path:str="~",file_extensions:str="")->str:
    """
    Find files modified within the last N days - optimized for Mac filesystem.
    Args:
        days_ago - Number of days to look back (default: 7)
        root_path - Starting directory (default: home directory)
        file_extensions - Comma-separated extensions to filter (e.g., "py,txt,md")
    Returns: JSON string with file details including path, modified time, and size
    Example: find_recent_files(days_ago=3, file_extensions="py,js")
    """
    root =Path(root_path).expanduser()
    if not root.exists():
        return json.dumps({"error": f"Path not found: {root_path}"})
    cutoff_time =datetime.now()-timedelta(days=days_ago) #Here am defining my time window for recent files based on user input
    results =[]

    #Initialize an empty set in case there's no input
    extensions =set()
    if file_extensions:
        raw_list =file_extensions.split(",")
        for ext in raw_list:
            clean_ext =ext.strip().lower()
            extensions.add(clean_ext)
        
    try:
        #Use iterative approach with depth limit for better performance
        search_queue =[(root,0)] #Track depth to prevent deep recursion
        while search_queue and len(results)<MAX_FILE_RESULTS*2:
            current_path,depth=search_queue.pop(0)
            
            if depth>MAX_SEARCH_DEPTH:
                continue
            try:
                for item in current_path.iterdir():
                    if should_skip_dir(item.name):
                        continue
                    if item.is_dir():
                        search_queue.append((item,depth+1))
                    elif item.is_file():
                        stat =item.stat()
                        mod_time =datetime.fromtimestamp(stat.st_mtime)
                        #Here am checking if within time range
                        if mod_time>=cutoff_time:
                            if extensions and item.suffix.lstrip('.').lower() not in extensions:
                                continue
                            results.append({
                                "path":str(item),
                                "name":item.name,
                                "modified":mod_time.strftime("%Y-%m-%d %H:%M:%S"),
                                "size_kb":round(stat.st_size / 1024, 2),
                                "extension":item.suffix
                            })
            except PermissionError:
                continue
        results.sort(key=lambda x: x["modified"], reverse=True)
        return json.dumps({
            "count": len(results),
            "files": results[:MAX_FILE_RESULTS],
            "search_limited": len(results) > MAX_FILE_RESULTS
        }, indent=2)
    except Exception as e:
        return json.dumps({"error":str(e)})

@mcp.tool()
def search_files_by_name(search_term:str,root_path:str="~",case_sensitive:bool=False)->str:
    """
    Search for files by name pattern - optimized with early termination.
    Args:
        search_term - Part of the filename to search for
        root_path - Starting directory (default: home directory)
        case_sensitive - Whether search should be case-sensitive (default: False)
    Returns: JSON string with matching files and their details
    Example: search_files_by_name("budget", case_sensitive=False)
    """
    root =Path(root_path).expanduser()
    if not root.exists():
        return json.dumps({"error": f"Path not found: {root_path}"})
    results =[]
    search =search_term if case_sensitive else search_term.lower()
    try:
        #Iterative search with depth limit
        search_queue = [(root, 0)]
        while search_queue and len(results) < 50: #Am stopping after finding 50 matches
            current_path, depth = search_queue.pop(0)
            if depth>MAX_SEARCH_DEPTH:
                continue
            try:
                for item in current_path.iterdir():
                    if should_skip_dir(item.name):
                        continue
                    if item.is_dir():
                        search_queue.append((item, depth + 1))
                    elif item.is_file():
                        #Apply case sensitivity to filename
                        name =item.name if case_sensitive else item.name.lower()
                        #Check if search term is in filename
                        if search in name:
                            stat =item.stat()
                            mod_time =datetime.fromtimestamp(stat.st_mtime)
                            results.append({
                                "path":str(item),
                                "name":item.name,
                                "modified":mod_time.strftime("%Y-%m-%d%H:%M:%S"),
                                "size_kb":round(stat.st_size/1024,2)
                            })
            except PermissionError:
                continue
        #Sort by most recent first
        results.sort(key=lambda x: x["modified"], reverse=True)
        return json.dumps({
            "count":len(results),
            "matches":results[:30]
        },indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def find_by_time_range(start_date:str,end_date:str,root_path:str="~")->str:
    """
    Find files modified within a specific date range.
    Args:
        start_date - Start date in format YYYY-MM-DD
        end_date - End date in format YYYY-MM-DD
        root_path - Starting directory
    Returns: JSON string with files modified in the date range
    Example: find_by_time_range("2024-01-20", "2024-01-25")
    """
    root =Path(root_path).expanduser()
    if not root.exists():
        return json.dumps({"error": f"Path not found: {root_path}"})
    
    try:
        #Parse dates with validation
        start =datetime.strptime(start_date, "%Y-%m-%d")
        end =datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        results =[]
        #Iterative search
        search_queue =[(root, 0)]
        while search_queue:
            current_path,depth=search_queue.pop(0)
            if depth>MAX_SEARCH_DEPTH:
                continue
            try:
                for item in current_path.iterdir():
                    if should_skip_dir(item.name):
                        continue
                    if item.is_dir():
                        search_queue.append((item, depth + 1))
                    elif item.is_file():
                        stat = item.stat()
                        mod_time = datetime.fromtimestamp(stat.st_mtime)
                        if start <= mod_time < end:
                            results.append({
                                "path": str(item),
                                "name": item.name,
                                "modified": mod_time.strftime("%Y-%m-%d %H:%M:%S"),
                                "size_kb": round(stat.st_size / 1024, 2)
                            })
            except PermissionError:
                continue
        
        results.sort(key=lambda x: x["modified"], reverse=True)
        
        return json.dumps({
            "date_range": f"{start_date} to {end_date}",
            "count": len(results),
            "files": results
        }, indent=2)
        
    except ValueError as e:
        return json.dumps({"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def read_file_content(file_path:str,max_lines:int = 100) -> str:
    """
    Read and return the content of a file with safety checks.
    Args:
        file_path - Path to the file to read
        max_lines - Maximum number of lines to return (default: 100)
    Returns: JSON string with file content and metadata
    Example: read_file_content("~/notes.txt", max_lines=50)
    """
    try:
        path =Path(file_path).expanduser()
        if not path.exists():
            return json.dumps({"error": "File not found"})
        #Here am checking if the file size before reading
        size_mb =path.stat().st_size/(1024 * 1024)
        if size_mb>10:
            return json.dumps({"error": f"File too large ({size_mb:.2f} MB). Maximum is 10 MB."})
        #Check if it's a text file
        mime_type, _ =mimetypes.guess_type(str(path))
        if mime_type and not mime_type.startswith('text'):
            return json.dumps({
                "error":"Not a text file",
                "mime_type":mime_type,
                "size_kb":round(path.stat().st_size / 1024, 2)
            })
        
        #Read file with error handling
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines =f.readlines()
            content =''.join(lines[:max_lines])
            return json.dumps({
                "path": str(path),
                "total_lines": len(lines),
                "displayed_lines": min(len(lines), max_lines),
                "content": content,
                "truncated": len(lines) > max_lines
            },indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_file_stats(file_path: str) -> str:
    """
    Get detailed statistics about a file - single stat() call for efficiency.
    Args: file_path - Path to the file
    Returns: JSON with comprehensive file metadata
    Example: get_file_stats("~/document.pdf")
    """
    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            return json.dumps({"error": "File not found"})
        #Single stat() call to get all metadata at once
        stat = path.stat()
        return json.dumps({
            "path": str(path),
            "name": path.name,
            "extension": path.suffix,
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "accessed": datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S"),
            "is_readable": os.access(path, os.R_OK),
            "is_writable": os.access(path, os.W_OK)
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def list_directory_contents(dir_path: str = "~", sort_by: str = "modified") -> str:
    """
    List all files in a directory with details - non-recursive for speed.
    Args:
        dir_path - Directory path (default: home directory)
        sort_by - Sort by 'modified', 'name', 'size', or 'created'
    Returns: JSON with directory contents
    Example: list_directory_contents("~/Documents", sort_by="size")
    """
    try:
        path = Path(dir_path).expanduser()
        if not path.exists() or not path.is_dir():
            return json.dumps({"error": "Directory not found"})
        
        items = []
        #Single level iteration for quick results
        for item in path.iterdir():
            if item.name.startswith('.'):
                continue
            stat = item.stat()
            items.append({
                "name": item.name,
                "path": str(item),
                "type": "directory" if item.is_dir() else "file",
                "size_kb": round(stat.st_size / 1024, 2) if item.is_file() else 0,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            })
        
        #Sort items based on user preference
        if sort_by == "modified":
            items.sort(key=lambda x: x["modified"], reverse=True)
        elif sort_by == "name":
            items.sort(key=lambda x: x["name"])
        elif sort_by == "size":
            items.sort(key=lambda x: x["size_kb"], reverse=True)
        
        return json.dumps({
            "directory": str(path),
            "count": len(items),
            "items": items
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def search_file_content(search_term: str, root_path: str = "~", file_extensions: str = "txt,md,py,js") -> str:
    """
    Search for text INSIDE files - grep-like functionality with safety limits.
    Args:
        search_term - Text to search for inside files
        root_path - Directory to search in
        file_extensions - Comma-separated extensions to search
    Returns: JSON with files containing the search term and matching lines
    Example: search_file_content("TODO", file_extensions="py,js")
    """
    try:
        root = Path(root_path).expanduser()
        if not root.exists():
            return json.dumps({"error": f"Path not found: {root_path}"})
        
        extensions = {ext.strip().lower() for ext in file_extensions.split(",")}
        results = []
        files_searched = 0
        
        #Iterative search with file count limit
        search_queue = [(root, 0)]
        
        while search_queue and len(results) < 20: #Stop after finding 20 files with matches
            current_path, depth = search_queue.pop(0)
            
            if depth > MAX_SEARCH_DEPTH:
                continue
            
            try:
                for item in current_path.iterdir():
                    if should_skip_dir(item.name):
                        continue
                    
                    if item.is_dir():
                        search_queue.append((item, depth + 1))
                    elif item.is_file():
                        #Check extension
                        if item.suffix.lstrip('.').lower() not in extensions:
                            continue
                        
                        #Skip large files to avoid memory issues
                        if item.stat().st_size > 10 * 1024 * 1024: #Skip files > 10MB
                            continue
                        
                        files_searched += 1
                        
                        try:
                            with open(item, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                
                                #Find matching lines with case-insensitive search
                                matches = [
                                    {"line_number": i + 1, "content": line.strip()}
                                    for i, line in enumerate(lines)
                                    if search_term.lower() in line.lower()
                                ]
                                
                                if matches:
                                    mod_time = datetime.fromtimestamp(item.stat().st_mtime)
                                    results.append({
                                        "path": str(item),
                                        "name": item.name,
                                        "modified": mod_time.strftime("%Y-%m-%d %H:%M:%S"),
                                        "match_count": len(matches),
                                        "matches": matches[:10] #Limit to 10 matches per file
                                    })
                        except:
                            continue #Skip files that can't be read as text
            except PermissionError:
                continue
        
        #Sort by number of matches (most relevant first)
        results.sort(key=lambda x: x["match_count"], reverse=True)
        
        return json.dumps({
            "search_term": search_term,
            "files_searched": files_searched,
            "files_with_matches": len(results),
            "results": results[:20]
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def analyze_workspace(root_path: str = "~") -> str:
    """
    Analyze your workspace and provide insights - optimized to skip system directories.
    Args: root_path - Directory to analyze
    Returns: JSON with workspace statistics and insights
    Example: analyze_workspace("~/Documents")
    """
    try:
        root = Path(root_path).expanduser()
        if not root.exists():
            return json.dumps({"error": f"Path not found: {root_path}"})
        
        stats = {
            "total_files": 0,
            "total_size_mb": 0,
            "extensions": defaultdict(int),
            "largest_files": [],
            "oldest_files": [],
            "newest_files": []
        }
        
        all_files = []
        
        #Iterative search to avoid recursion limits
        search_queue = [(root, 0)]
        
        while search_queue:
            current_path, depth = search_queue.pop(0)
            
            if depth > MAX_SEARCH_DEPTH:
                continue
            
            try:
                for item in current_path.iterdir():
                    if should_skip_dir(item.name):
                        continue
                    
                    if item.is_dir():
                        search_queue.append((item, depth + 1))
                    elif item.is_file():
                        stat = item.stat()
                        size_mb = stat.st_size / (1024 * 1024)
                        mod_time = datetime.fromtimestamp(stat.st_mtime)
                        
                        stats["total_files"] += 1
                        stats["total_size_mb"] += size_mb
                        stats["extensions"][item.suffix or "no_extension"] += 1
                        
                        all_files.append({
                            "path": str(item),
                            "name": item.name,
                            "size_mb": round(size_mb, 2),
                            "modified": mod_time.strftime("%Y-%m-%d %H:%M:%S")
                        })
            except PermissionError:
                continue
        
        #Get insights - largest files
        all_files.sort(key=lambda x: x["size_mb"], reverse=True)
        stats["largest_files"] = all_files[:10]
        
        #Oldest files
        all_files.sort(key=lambda x: x["modified"])
        stats["oldest_files"] = all_files[:10]
        
        #Newest files
        stats["newest_files"] = all_files[-10:][::-1]
        
        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        stats["extensions"] = dict(sorted(stats["extensions"].items(), key=lambda x: x[1], reverse=True)[:15])
        
        return json.dumps(stats, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def find_duplicate_files(root_path: str = "~", min_size_kb: int = 10) -> str:
    """
    Find duplicate files based on name and size - memory efficient implementation.
    Args:
        root_path - Directory to search
        min_size_kb - Minimum file size to consider (default: 10 KB)
    Returns: JSON with duplicate file groups and potential savings
    Example: find_duplicate_files("~/Downloads", min_size_kb=100)
    """
    try:
        root = Path(root_path).expanduser()
        if not root.exists():
            return json.dumps({"error": f"Path not found: {root_path}"})
        
        file_groups = defaultdict(list)
        
        #Iterative search
        search_queue = [(root, 0)]
        
        while search_queue:
            current_path, depth = search_queue.pop(0)
            
            if depth > MAX_SEARCH_DEPTH:
                continue
            
            try:
                for item in current_path.iterdir():
                    if should_skip_dir(item.name):
                        continue
                    
                    if item.is_dir():
                        search_queue.append((item, depth + 1))
                    elif item.is_file():
                        size = item.stat().st_size
                        size_kb = size / 1024
                        
                        if size_kb < min_size_kb:
                            continue
                        
                        #Group by (name, size) tuple
                        key = (item.name, size)
                        file_groups[key].append(str(item))
            except PermissionError:
                continue
        
        duplicates = []
        potential_savings = 0
        
        #Find groups with multiple files
        for (name, size), paths in file_groups.items():
            if len(paths) > 1:
                savings_mb = (size / (1024 * 1024)) * (len(paths) - 1)
                potential_savings += savings_mb
                
                duplicates.append({
                    "name": name,
                    "size_kb": round(size / 1024, 2),
                    "count": len(paths),
                    "locations": sorted(paths),
                    "potential_savings_mb": round(savings_mb, 2)
                })
        
        duplicates.sort(key=lambda x: x["potential_savings_mb"], reverse=True)
        
        return json.dumps({
            "duplicate_sets": duplicates,
            "total_duplicates": len(duplicates),
            "potential_savings_mb": round(potential_savings, 2)
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def suggest_file_organization(root_path: str = "~/Downloads") -> str:
    """
    Analyze a messy directory and suggest organization - single level scan only.
    Args: root_path - Directory to analyze
    Returns: JSON with organization suggestions
    Example: suggest_file_organization("~/Downloads")
    """
    try:
        root = Path(root_path).expanduser()
        
        if not root.exists() or not root.is_dir():
            return json.dumps({"error": "Directory not found"})
        #File categories optimized for common use cases
        categories = {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic"],
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".pages"],
            "Spreadsheets": [".xlsx", ".xls", ".csv", ".ods", ".numbers"],
            "Presentations": [".pptx", ".ppt", ".key", ".odp"],
            "Videos": [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".m4v"],
            "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".dmg"],
            "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".sh", ".ipynb"],
            "Executables": [".exe", ".dmg", ".app", ".deb", ".rpm", ".pkg"]
        }
        
        file_counts = defaultdict(int)
        file_lists = defaultdict(list)
        
        #Only scan immediate children for quick analysis
        for item in root.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                ext = item.suffix.lower()
                categorized = False
                
                for category, extensions in categories.items():
                    if ext in extensions:
                        file_counts[category] += 1
                        file_lists[category].append(item.name)
                        categorized = True
                        break
                
                if not categorized:
                    file_counts["Other"] += 1
                    file_lists["Other"].append(item.name)
        
        suggestions = []
        for category, count in file_counts.items():
            if count >= 3: #Only suggest if 3+ files of same type
                suggestions.append({
                    "folder_name": category,
                    "file_count": count,
                    "action": f"Create '{category}' folder and move {count} files",
                    "example_files": file_lists[category][:5]
                })
        suggestions.sort(key=lambda x: x["file_count"], reverse=True)
        total_files = sum(file_counts.values())
        return json.dumps({
            "current_state": {
                "directory": str(root),
                "total_files": total_files,
                "breakdown": dict(file_counts)
            },
            "suggestions": suggestions,
            "recommendation": (
                f"Found {len(suggestions)} categories with 3+ files. "
                f"Creating folders for these categories would improve organization."
                if suggestions
                else "Directory is already well-organized or has too few files to categorize."
            )
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})